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
from .solarwinds_papertrail import install_solarwinds_papertrail
from .util import run_cmd
import ringmaster.k8s as k8s

debug = False


def download(url, filename):
    downloaded = requests.get(url, allow_redirects=True)
    open(filename, 'wb').write(downloaded.content)


def load_databag(databag_file):
    # users write values as JSON to this file and they are added to the
    # databag incrementally
    _, intermediate_databag_file = tempfile.mkstemp(suffix="json", prefix="ringmaster")
    _, eksctl_databag_file = tempfile.mkstemp(suffix="json", prefix="ringmaster-eksctl")

    # general program settings
    data = {
        "msg_up_to_date": constants.MSG_UP_TO_DATE,
    }

    # load values from user
    if os.path.exists(databag_file):
        with open(databag_file) as f:
            data.update(yaml.safe_load(f))
    else:
        logger.warning(f"missing databag file: {databag_file}")

    # per-run program specific data
    data.update({
        constants.KEY_INTERMEDIATE_DATABAG: intermediate_databag_file,
        constants.KEY_EKSCTL_DATABAG: eksctl_databag_file,
        "debug": "debug" if debug else "",
        "name": os.path.basename(os.getcwd()),
    })

    logger.debug(f"loaded databag contents: {data}")
    return data


def load_intermediate_databag(data):
    intermediate_databag_file = data[constants.KEY_INTERMEDIATE_DATABAG]
    if os.path.getsize(intermediate_databag_file):
        # grab stashed databag
        logger.debug(f"loading databag left by last stage from {intermediate_databag_file}")
        with open(intermediate_databag_file, "r") as json_file:
            extra_data = json.load(json_file)

        logger.debug(f"loaded {len(extra_data)} items: {extra_data}")
        data.update(extra_data)

        # empty the bag for next iteration
        open(intermediate_databag_file, 'w').close()


def do_bash_script(stage, data):
    # bash scripts
    for bash_script in glob.glob(f"{stage}/*{constants.PATTERN_BASH}"):
        logger.info(f"bash script: {bash_script}")
        run_cmd(f"bash {bash_script}", data)

        load_intermediate_databag(data)
        load_eksctl_databag(data)


def do_cloud_formation(stage, verb, data):
    # cloudformation
    for cloudformation_file in glob.glob(f"{stage}/*{constants.PATTERN_CLOUDFORMATION_FILE}"):
        logger.info(f"cloudformation {cloudformation_file}")
        data.update(run_cloudformation(cloudformation_file, verb, data))


def do_kubectl(stage, verb, data):
    # kubectl (will pre-process yaml files and replace ${variable} with
    # variable from databag if present - looked at Kustomizer, too komplicated
    for kubectl_file in glob.glob(f"{stage}/*{constants.PATTERN_KUBECTL_FILE}"):
        logger.info(f"kubectl: {kubectl_file}")
        k8s.run_kubectl(kubectl_file, verb, data)


def do_solarwinds_papertrail(stage, data):
    for config_file in glob.glob(f"{stage}/*{constants.PATTERN_SOLARWINDS_PAPERTRAIL_FILE}"):
        logger.info(f"solarwinds papertrail: {config_file}")
        install_solarwinds_papertrail(config_file, data)


def do_kustomization(stage, verb):
    for kustomization_file in glob.glob(f"{stage}/*{constants.PATTERN_KUSTOMIZATION_FILE}"):
        logger.info(f"kustomization: {kustomization_file}")
        kubectl_cmd = "apply" if verb == constants.UP_VERB or verb == constants.USER_UP_VERB else "delete"
        k8s.run_kustomizer(os.path.dirname(kustomization_file), kubectl_cmd)


def do_stage(data, stage, verb):
    do_kustomization(stage, verb)
    do_cloud_formation(stage, verb, data)
    do_kubectl(stage, verb, data)
    do_solarwinds_papertrail(stage, data)
    do_bash_script(stage, data)


def down(goto):
    return run_dir(constants.DOWN_VERB, goto)


def up(goto):
    return run_dir(constants.UP_VERB,goto)


def user_up(goto):
    return run_dir(constants.USER_UP_VERB,goto)


def user_down(goto):
    return run_dir(constants.USER_DOWN_VERB, goto)


def run_dir(verb, goto):
    if os.path.exists(verb):
        logger.debug(f"found: {verb}")
        started = False

        if goto == "0010":
            data = load_databag(constants.DATABAG_FILE)
        else:
            data = load_databag(constants.OUTPUT_DATABAG_FILE)

        # for some reason the default order is reveresed when using ranges
        for stage in sorted(glob.glob(f"./{verb}/[0-9][0-9][0-9][0-9]")):
            if not started:
                number = os.path.basename(stage)
                if number == goto:
                    started = True

            if started:
                logger.debug(f"stage: {stage}")
                do_stage(data, stage, verb)

        if not started:
            logger.error(f"goto dir - not found: {goto}")

        # cleanup
        logger.debug("delete intermediate databag")
        os.unlink(data[constants.KEY_INTERMEDIATE_DATABAG])
        logger.debug("delete eksctl databag")
        os.unlink(data[constants.KEY_EKSCTL_DATABAG])

        # save the updated databag for use in normal operation
        with open(constants.OUTPUT_DATABAG_FILE, "w") as f:
            f.write("# generated by ringmaster, do not edit!\n")
            yaml.dump(data, f)
    else:
        logger.error(f"missing directory: {verb}")