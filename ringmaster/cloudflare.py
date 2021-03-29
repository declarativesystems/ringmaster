# Copyright 2020 Declarative Systems Pty Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import CloudFlare
import ringmaster.constants as constants
import ringmaster.util as util
import ringmaster.aws as aws
from loguru import logger
import yaml
import re
import tempfile
import os
import json


def get_cf():
    """
    Get an authenticated cloudflare API instance. Authentication resolved in
    order from:
    1. `.cloudflare.cfg`
    2. Environment variables

    @see
    https://github.com/cloudflare/python-cloudflare#providing-cloudflare-username-and-api-key
    """
    return CloudFlare.CloudFlare()


def list_contains_dict_value(data, key, target):
    found = False
    logger.debug(f"filtering list for dict value: {key}=={target}")
    for hostname in data.get(key, []):
        if re.search(f"^{re.escape(target)}$", hostname):
            found = True
            break

    return found


def create_csr(hostname):
    _, csr_temp = tempfile.mkstemp()
    _, private_key_temp = tempfile.mkstemp()
    cmd = f"""openssl \
        req -new -newkey rsa:2048 -nodes \
        -out {csr_temp} \
        -keyout {private_key_temp} \
        -subj "/C=US/ST=California/L=/O=/CN={hostname}"
    """
    util.run_cmd(cmd)

    # read both files into memory and return them, deleteing the tempfiles
    with open(csr_temp) as f:
        csr_data = f.read()

    with open(private_key_temp) as f:
        private_key_data = f.read()

    os.remove(csr_temp)
    os.remove(private_key_temp)

    return csr_data, private_key_data


def ensure_origin_ca_cert(cf, verb, origin_certs, hostname, cb):
    """create origin CA cert for `domain` if needed"""

    def hostname_filter(data):
        return list_contains_dict_value(data, "hostnames", hostname)
    pass

    origin_ca_cert = list(filter(hostname_filter, origin_certs))

    # We cannot update/create missing secrets for origins that have
    # already been provisioned as the certificate private key is only
    # available while the CSR is being processed. If secret needs to
    # autohealing capability would have to delete the existing origin
    # CA and sign a new cert.
    # TLDR - To re-create secret delete (revoke) the Origin CA cert and
    # the secret in secrets manager, then re-run
    certificate = None
    private_key_data = None
    if verb == constants.DOWN_VERB and origin_ca_cert:
        cert_id = origin_ca_cert[0]["id"]
        logger.info(f"Deleting Origin CA cert: {hostname}/{cert_id}")
        cf.certificates.delete(cert_id)
    elif verb == constants.UP_VERB and not origin_ca_cert:
        logger.debug(f"Creating Origin CA cert: {hostname}")
        csr_data, private_key_data = create_csr(hostname)
        res = cf.certificates.post(data={
            "hostnames": [hostname, f"*.{hostname}"],
            "csr": csr_data,
            "request_type": "origin-rsa",
        })
        certificate = res["certificate"]
        logger.info(res.get("certificate"))
        logger.info(res.get("csr"))
    else:
        logger.info(constants.MSG_UP_TO_DATE)

    logger.debug(f"processing callback for {hostname}")
    cb(verb, hostname, certificate, private_key_data)


# walkthru: https://blog.cloudflare.com/cloudflare-ca-encryption-origin/
def origin_ca_certs(cf, zone_id, verb, zone_data, cb):
    # create each requested cert (if stack is going down just delete
    # everything to avoid creating orphans
    certs_to_ensure = zone_data.get("origin_ca_certs", [])
    if certs_to_ensure:
        # get the list of all origin ca certs for this domain
        origin_certs = cf.certificates.get(params={"zone_id": zone_id})

        for domain in certs_to_ensure:
            logger.debug(f"ensure wildcard origin CA cert: {domain}")
            ensure_origin_ca_cert(cf, verb, origin_certs, domain, cb)


def get_zone_id(cf, zone_name):
    """get the zone_id for a zone name or `False` if not exist"""
    params = {"name": zone_name, "per_page": 1}
    zones = cf.zones.get(params=params)
    try:
        zone_id = zones[0]['id']
    except KeyError:
        raise RuntimeError(f"zone {zone_name} not visible in cloudflare! - check setup/permissions")

    logger.debug(f"cloudflare resolved zone {zone_name} -> {zone_id}")
    return zone_id


def zone_settings(cf, zone_id, verb, yaml_data):
    """zone-wide cloudflare settings (strict mode ssl)"""

    # list of dict -> dict
    if verb == constants.UP_VERB:
        settings_list_of_dict = cf.zones.settings.get(zone_id)
        settings_dict = {item['id']: item["value"] for item in settings_list_of_dict}
        logger.debug(f"settings for zone_id {zone_id}: {settings_dict}")
        for key, value in yaml_data.get("settings", {}).items():
            if settings_dict.get(key) == value:
                logger.debug(f"up-to-date: {key}=>{value}")
            else:
                logger.debug(f"setting: {key}=>{value}")
                getattr(cf.zones.settings, key).patch(zone_id, data={"value": value})
    else:
        logger.info("skipping cloudformation zone settings")


def edge_certs(cf, zone_id, verb, yaml_data):
    """create or delete the named edge certificates. Edge certs are 100%
    managed by cloudflare so the orgin never knows about or sees them"""
    certs = cf.zones.ssl.certificate_packs.get(zone_id)

    for hostname in yaml_data.get("edge_certs", []):
        logger.debug(f"edge cert: {hostname}")

        def hostname_filter(data):
            return list_contains_dict_value(data, "hosts", hostname)
        pass

        issued = list(filter(hostname_filter, certs))
        if verb == constants.UP_VERB and not issued:
            logger.info(f"[cloudflare] creating edge certificate: {hostname}")
            cf.zones.ssl.certificate_packs.order.post(zone_id, data={
                "type": "advanced",
                "hosts": [yaml_data["zone_name"], hostname],
                "validation_method": "txt",
                "validity_days": 365,
                "certificate_authority": "digicert",
            })
        elif verb == constants.DOWN_VERB and issued:
            cert_id = issued[0]["id"]
            logger.info(f"[cloudflare] deleting edge certificate: {hostname}/{cert_id}")
            cf.zones.ssl.certificate_packs.delete(zone_id, cert_id)
        else:
            logger.info(constants.MSG_UP_TO_DATE)


def do_cloudflare(filename, verb, data=None):
    logger.info(f"cloudflare: {filename}")

    try:
        processed_file = util.substitute_placeholders_from_file_to_file(filename, "#", verb, data)
        with open(processed_file) as f:
            yaml_data = yaml.safe_load(f)
            logger.debug(f"cloudflare file processed OK")

        prefix = yaml_data.get("aws").get("secrets_manager_prefix") or ""
        logger.debug(f"aws secretsmanager prefix: {prefix}")

        # callback to run when a certificate has been created
        # for now, always creates an AWS secret
        def cb(_verb, hostname, certificate_data, private_key_data):
            secret_string = json.dumps({
                    "tls.crt": certificate_data,
                    "tls.key": private_key_data,
                }
            )
            secret = {
                "name": f"{prefix}tls-{hostname.replace('.', '-')}",
                "value": secret_string,
            }

            if (_verb == constants.UP_VERB and certificate_data and private_key_data) \
                    or _verb == constants.DOWN_VERB:
                aws.ensure_secret(data, _verb, secret)
            else:
                logger.info(f"[cloudflare-aws-callback] no update required for: {hostname}")

        # lookup zone id now as needed everywhere
        cf = get_cf()
        zone_id = get_zone_id(cf, yaml_data["zone_name"])

        origin_ca_certs(cf, zone_id, verb, yaml_data, cb)
        edge_certs(cf, zone_id, verb, yaml_data)
        zone_settings(cf, zone_id, verb, yaml_data)
    # except RuntimeError as e:
    #     if verb == constants.DOWN_VERB:
    #         logger.warning(f"kubectl error - moving on: {e}")
    #     else:
    #         raise e
    except KeyError as e:
        if verb == constants.DOWN_VERB:
            logger.warning(f"missing key - moving on: {e}")
        else:
            raise e
