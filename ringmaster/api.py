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

from ringmaster import constants as constants
from .aws import run_cloudformation


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


def convert_dict_values_to_string(data):
    # all values passed to os.environ must be strings, avoid unwanted yaml help
    for key in data:
        data[key] = str(data[key])


def merge_env(data):
    env = os.environ.copy()
    env.update(constants.RINGMASTER_ENV)
    env.update(data)

    convert_dict_values_to_string(env)
    return env


def run_cmd(cmd, data):
    env = merge_env(data)
    logger.debug(f"merged environment: {env}")

    with subprocess.Popen(cmd,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          shell=True,
                          env=env) as proc:
        while True:
            output = proc.stdout.readline()
            if proc.poll() is not None:
                break
            if output:
                logger.log("OUTPUT", output.decode("UTF-8").strip())
        rc = proc.poll()
        logger.debug(f"result: {rc}")
        return rc


def do_stage(data, intermediate_databag_file, stage, verb):
    # bash scripts
    for shell_script in glob.glob(f"{stage}/*{constants.PATTERN_BASH}"):
        logger.debug(f"shell script: {shell_script}")
        logger.info(shell_script)
        rc = run_cmd(f"bash {shell_script}", data)
        if rc:
            # bomb out
            raise RuntimeError(f"script {shell_script} - non zero exit status: {rc}")
        elif os.path.getsize(intermediate_databag_file):
            # grab stashed databag
            logger.debug(f"loading databag left by last stage from {intermediate_databag_file}")
            with open(intermediate_databag_file) as json_file:
                extra_data = json.load(json_file)

            logger.debug(f"loaded {len(extra_data)} items: {extra_data}")
            data.update(extra_data)

            # empty the bag for next iteration
            open(intermediate_databag_file, 'w').close()

    # cloudformation
    for cloudformation_file in glob.glob(f"{stage}/*{constants.PATTERN_CLOUDFORMATION_FILE}"):
        logger.debug(f"cloud formation: {cloudformation_file}")
        logger.info(cloudformation_file)

        data.update(run_cloudformation(cloudformation_file, verb, data))


def down():
    return run_dir(constants.DOWN_VERB)


def up():
    return run_dir(constants.UP_VERB)


def run_dir(verb):
    # users write values as JSON to this file and they are added to the
    # databag incrementally
    _, intermediate_databag_file = tempfile.mkstemp(suffix="json", prefix="ringmaster")
    data = {
        "intermediate_databag_file":  intermediate_databag_file,
        "msg_up_to_date": constants.MSG_UP_TO_DATE,
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

