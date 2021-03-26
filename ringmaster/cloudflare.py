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


def origin_ca_list_contains_hostname(data, target):
    found = False
    for hostname in data.get("hostnames", []):
        if re.search(target, hostname):
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
        return origin_ca_list_contains_hostname(data, hostname)
    pass

    origin_ca_cert = list(filter(hostname_filter, origin_certs))

    # We cannot update/create missing secrets for origins that have
    # already been provisioned as the certificate private key is only
    # available while the CSR is being processed. If secret needs to
    # autohealing capability would have to delete the existing origin
    # CA and sign a new cert.
    # TLDR - To re-create secret delete (revoke) the Origin CA cert and
    # the secret in secrets manager, then re-run
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

        logger.info(res.get("certificate"))
        logger.info(res.get("csr"))
        cb(hostname, res["certificate"], private_key_data)
    else:
        logger.info(constants.MSG_UP_TO_DATE)

# walkthru: https://blog.cloudflare.com/cloudflare-ca-encryption-origin/
def origin_ca_certs(verb, zone_data, cb):
    cf = get_cf()
    zone_name = zone_data["zone_name"]
    zone_id = get_zone_id(cf, zone_name)

    if not zone_id:
        raise RuntimeError("zone {data['zone_name']} not visible in cloudflare! - check setup/permissions")

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
        zone_id = False

    logger.debug(f"cloudflare resolved zone {zone_name} -> {zone_id}")
    return zone_id


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
        def cb(hostname, certificate_data, private_key_data):
            secret_string = json.dumps({
                    "tls.crt": certificate_data,
                    "tls.key": private_key_data,
                }
            )

            secret = {
                "name": f"{prefix}tls-{hostname.replace('.', '-')}",
                "value": secret_string
            }

            # make the secret..
            aws.ensure_secret(data, constants.UP_VERB, secret)

        origin_ca_certs(verb, yaml_data, cb)
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