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


RECOMMENDED_EKSCTL_VERSION="0.31.0-rc.1"
UP_DIR = "up"
DOWN_DIR = "down"
DATABAG_FILE = "databag.yaml"
RES_DIR = "res"
RES_AWS_DIR = os.path.join(RES_DIR, "aws")
RES_AWS_IAM_DIR = os.path.join(RES_AWS_DIR, "iam")
RINGMASTER_ENV = {
    "res_dir": RES_DIR,
    "res_aws_dir": RES_AWS_DIR,
    "res_aws_iam_dir": RES_AWS_IAM_DIR,
}


def download(url, filename):
    downloaded = requests.get(url, allow_redirects=True)
    open(filename, 'wb').write(downloaded.content)

def aws_init():
    vendor_cfn_dir = ".vendor/aws/cloudformation"
    logger.info("Initialising ringmaster for AWS...")
    pathlib.Path(vendor_cfn_dir).mkdir(parents=True, exist_ok=True)
    vendor_vpc_cfn=os.path.join(vendor_cfn_dir, "vpc.yaml")
    download(vendor_vpc_cfn)

def xxup():
    check_requirements()

def load_databag(data):
    if os.path.exists(DATABAG_FILE):
        with open(DATABAG_FILE) as f:
            data.update(yaml.safe_load(f))

        logger.debug(f"loaded databag contents: {data}")

    else:
        logger.warning(f"missing databag: {DATABAG_FILE}")


def convert_dict_values_to_string(data):
    # all values passed to os.environ must be strings, avoid unwanted yaml help
    for key in data:
        data[key] = str(data[key])


def merge_env(data):
    env = os.environ.copy()
    env.update(RINGMASTER_ENV)
    env.update(data)

    convert_dict_values_to_string(env)
    return env


def run_cmd(data, cmd):
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


def do_stage(data, intermediate_databag_file, stage):
    for shell_script in glob.glob(f"{stage}/*.sh"):
        logger.debug(f"shell script: {shell_script}")
        logger.info(shell_script)
        rc = run_cmd(data, f"bash {shell_script}")
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


def down():
    return run_dir(DOWN_DIR)


def up():
    return run_dir(UP_DIR)

def run_dir(run_dir):
    # users write values as JSON to this file and they are added to the
    # databag incrementally
    _, intermediate_databag_file = tempfile.mkstemp(suffix="json", prefix="ringmaster")
    data = {
        "intermediate_databag_file":  intermediate_databag_file
    }
    load_databag(data)

    if os.path.exists(run_dir):
        logger.debug(f"found: {run_dir}")
        # for some reason the default order is reveresed when using ranges
        for stage in sorted(glob.glob(f"./{run_dir}/[0-9][0-9][0-9][0-9]")):
            logger.debug(f"stage: {stage}")
            do_stage(data, intermediate_databag_file, stage)
    else:
        logger.error(f"missing directory: {run_dir}")

    # cleanup
    os.unlink(intermediate_databag_file)



def check_requirements():
    eksctl_version = subprocess.check_output(['eksctl', 'version'])
    aws_version = subprocess.check_output(['aws', '--version'])
    helm_version = subprocess.check_output(['helm', 'version'])
    kubectl_version = subprocess.check_output(["kubectl", "version", "--short"])

    # TODO 1) bomb out on bad versions 2) option to skip bomb out
    logger.info(f"eksctl: ${eksctl_version}")
    logger.info(f"aws: ${aws_version}")
    logger.info(f"helm: ${helm_version}")
    logger.info(f"helm: ${kubectl_version}")