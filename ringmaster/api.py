import subprocess
import pathlib
import requests
import os
import glob
import yaml
import json
import sys
import tempfile
from loguru import logger
import re
from ringmaster import constants as constants
from .aws import run_cloudformation
from .aws import load_eksctl_databag
from .util import substitute_placeholders_in_file
from .solarwinds_papertrail import install_solarwinds_papertrail
from .util import run_cmd

def download(url, filename):
    downloaded = requests.get(url, allow_redirects=True)
    open(filename, 'wb').write(downloaded.content)


def load_databag(data):
    if os.path.exists(constants.DATABAG_FILE):
        with open(constants.DATABAG_FILE) as f:
            data.update(yaml.safe_load(f))

        logger.debug(f"loaded databag contents: {data}")

    else:
        logger.warning(f"missing databag: {constants.DATABAG_FILE}")



def load_intermediate_databag(intermediate_databag_file, data):
    if os.path.getsize(intermediate_databag_file):
        # grab stashed databag
        logger.debug(f"loading databag left by last stage from {intermediate_databag_file}")
        with open(intermediate_databag_file) as json_file:
            extra_data = json.load(json_file)

        logger.debug(f"loaded {len(extra_data)} items: {extra_data}")
        data.update(extra_data)

        # empty the bag for next iteration
        open(intermediate_databag_file, 'w').close()


def run_kubectl(kubectl_file, verb, data):
    # substitute ${...} variables from databag, bomb out if any missing
    processed_file = substitute_placeholders_in_file(kubectl_file, data)
    logger.debug(f"kubectl processed file: {processed_file}")

    if verb == constants.UP_VERB:
        kubectl_cmd = "apply"
    elif verb == constants.DOWN_VERB:
        kubectl_cmd = "delete"
    else:
        raise ValueError(f"invalid verb: {verb}")

    run_cmd(f"kubectl {kubectl_cmd} -f {processed_file}", data)


def do_stage(data, intermediate_databag_file, stage, verb):
    # bash scripts
    for bash_script in glob.glob(f"{stage}/*{constants.PATTERN_BASH}"):
        logger.debug(f"shell script: {bash_script}")
        logger.info(bash_script)
        run_cmd(f"bash {bash_script}", data)

        load_intermediate_databag(intermediate_databag_file, data)
        load_eksctl_databag(data['eksctl_databag_file'], data)

    # cloudformation
    for cloudformation_file in glob.glob(f"{stage}/*{constants.PATTERN_CLOUDFORMATION_FILE}"):
        logger.debug(f"Cloudformation: {cloudformation_file}")
        logger.info(cloudformation_file)

        data.update(run_cloudformation(cloudformation_file, verb, data))

    # kubectl (will pre-process yaml files and replace ${variable} with
    # variable from databag if present - looked at Kustomizer, too komplicated
    for kubectl_file in glob.glob(f"{stage}/*{constants.PATTERN_KUBECTL_FILE}"):
        logger.debug(f"kubectl: {kubectl_file}")
        logger.info(kubectl_file)

        run_kubectl(kubectl_file, verb, data)

    #
    # solarwinds papertrail
    #
    for config_file in glob.glob(f"{stage}/*{constants.PATTERN_SOLARWINDS_PAPERTRAIL_FILE}"):
        logger.debug(f"solarwinds papertrail: {config_file}")
        install_solarwinds_papertrail(config_file, data)

def down():
    return run_dir(constants.DOWN_VERB)


def up():
    return run_dir(constants.UP_VERB)


def run_dir(verb):
    # users write values as JSON to this file and they are added to the
    # databag incrementally
    _, intermediate_databag_file = tempfile.mkstemp(suffix="json", prefix="ringmaster")
    _, eksctl_databag_file = tempfile.mkstemp(suffix="json", prefix="ringmaster-eksctl")
    data = {
        "intermediate_databag_file":  intermediate_databag_file,
        "eksctl_databag_file": eksctl_databag_file,
        "msg_up_to_date": constants.MSG_UP_TO_DATE,
        "name": os.path.basename(os.getcwd())
    }
    load_databag(data)

    if os.path.exists(verb):
        logger.debug(f"found: {verb}")
        # for some reason the default order is reveresed when using ranges
        for stage in sorted(glob.glob(f"./{verb}/[0-9][0-9][0-9][0-9]")):
            logger.debug(f"stage: {stage}")
            do_stage(data, intermediate_databag_file, stage, verb)
    else:
        logger.error(f"missing directory: {verb}")

    # cleanup
    os.unlink(intermediate_databag_file)
    os.unlink(eksctl_databag_file)

