import re
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
import boto3
import snakecase
import pathlib
from ringmaster import constants as constants
from cfn_tools import load_yaml, dump_yaml
import botocore.exceptions
from halo import Halo

from ringmaster.util import flatten_nested_dict

RECOMMENDED_EKSCTL_VERSION="0.31.0-rc.1"

# AWS/boto3 API error messages to look for. Use partial regex to protect
# against upstream changes as much as we can
ERROR_UP_TO_DATE = r"No updates are to be performed"
ERROR_AWS = r"encountered a terminal failure state"
ERROR_MISSING = r"does not exist"

def aws_init():
    vendor_cfn_dir = ".vendor/aws/cloudformation"
    logger.info("Initialising ringmaster for AWS...")
    pathlib.Path(vendor_cfn_dir).mkdir(parents=True, exist_ok=True)
    vendor_vpc_cfn=os.path.join(vendor_cfn_dir, "vpc.yaml")
    # download(vendor_vpc_cfn)


def filename_to_stack_name(cloudformation_file, data):
    return os.path.basename(cloudformation_file)\
        .replace(constants.PATTERN_CLOUDFORMATION_FILE, "")

def load_eksctl_databag(eksctl_databag_file, data):
    if os.path.getsize(eksctl_databag_file):
        logger.debug(f"loading eksctl cluster info from from {eksctl_databag_file}")
        with open(eksctl_databag_file) as json_file:
            # strip outer array
            extra_data = json.load(json_file)[0]

        logger.debug(f"loaded items:{len(extra_data)} data:{extra_data}")
        data.update(flatten_nested_dict(extra_data))

        # empty the bag so we know to ignore it
        open(eksctl_databag_file, 'w').close()

def cloudformation_param(key, value):
    return {
        "ParameterKey": key,
        "ParameterValue": value
    }


def stack_params(cloudformation_file, data):
    # we can only insert stack parameters that are defined in YAML or cfn
    # will barf, so grab the parameter names from the CFN file and then
    # grab the corresponding parameters from the databag. If anything is
    # missing bomb out now before CFN does.
    # parse with cfn_flip as pyyaml cant handle things like `!Ref`
    # https://stackoverflow.com/a/55349491/3441106
    cloudformation = load_yaml(pathlib.Path(cloudformation_file).read_text())

    params = []

    if "Parameters" in cloudformation:
        for cfn_param in cloudformation["Parameters"]:
            logger.debug(f"processing parameter: {cfn_param}")

            # cloudformation parameters are usually camel case but databag
            # parameters are usually snake case - use an exact match followed
            # by snake case
            if data.get(cfn_param):
                params.append(cloudformation_param(cfn_param, data.get(cfn_param)))
            elif data.get(snakecase.convert(cfn_param)):
                params.append(cloudformation_param(cfn_param, data.get(snakecase.convert(cfn_param))))
            elif cloudformation["Parameters"][cfn_param].get("Default"):
                logger.debug(f"Using cloudformation default for {cfn_param}")
            else:
                raise RuntimeError(f"Cloudformation file:{cloudformation_file} missing parameter:{cfn_param}")
    else:
        logger.debug(f"no Parameters section in {cloudformation_file}")

    return params


def stack_exists(stack_name):
    client = boto3.client('cloudformation')
    logger.debug(f"cloudformation - describe_stacks: {stack_name}")
    try:
        response = client.describe_stacks(
            StackName=stack_name,
        )
        logger.debug(f"cloudformation - nothing thrown, response: {response}")
        exists = True
    except botocore.exceptions.ClientError as e:
        logger.debug(f"cloudformation exception - missing stack: {e}")
        if re.search(ERROR_MISSING, str(e), re.IGNORECASE):
            # normal AWS response for a missing stack
            exists = False
        else:
            # no idea... AWS broken?
            raise e

    logger.debug(f"cloudformation stack:{stack_name} exists:{exists}")
    return exists


def cloudformation_outputs(stack_name, prefixed_stack_name, data):
    client = boto3.client('cloudformation')
    response = client.describe_stacks(
        StackName=prefixed_stack_name,
    )
    intermediate_databag = {}
    if "Stacks" in response and "Outputs" in response["Stacks"][0]:
        outputs = response["Stacks"][0]["Outputs"]
        logger.debug(f"cloudformation - checking outputs: {outputs}")
        for output in outputs:
            # replace the value of `{prefixed_stack_name}_` with `{stack_name}_`
            # eg foo-infra-efs --> infa_efs
            # this lets us reference variables in the stack without having to
            # adjust the name each time and avoids tricks like eval in bash.
            # the downside of this is you need to know what stack generated the
            # output name
            key_name = output["ExportName"].lower().replace("-", "_")
            key_name = key_name.replace(f"{prefixed_stack_name}_", f"{stack_name}_")

            string_value = str(output["OutputValue"])
            intermediate_databag[key_name] = string_value

    logger.debug(f"cloudformation - outputs:{len(intermediate_databag)} value: {intermediate_databag}")
    return intermediate_databag


def run_cloudformation(cloudformation_file, verb, data):
    stack_name = filename_to_stack_name(cloudformation_file, data)
    prefixed_stack_name = f"{data['name']}-{stack_name}"
    params = stack_params(cloudformation_file, data)
    client = boto3.client('cloudformation')
    exists = stack_exists(prefixed_stack_name)
    template_body = pathlib.Path(cloudformation_file).read_text()
    act = False

    if exists and verb == constants.UP_VERB:
        # update
        def ensure_fn():
            return client.update_stack(
                StackName=prefixed_stack_name,
                TemplateBody=template_body,
                Parameters=params,
                Capabilities=['CAPABILITY_NAMED_IAM'],
            )

        waiter_name = "stack_update_complete"
        act = True
    elif exists and verb == constants.DOWN_VERB:
        # delete
        def ensure_fn():
            return client.delete_stack(
                StackName=prefixed_stack_name,
            )
        waiter_name = "stack_delete_complete"
        act = True
    elif not exists and verb == constants.UP_VERB:
        # create
        def ensure_fn():
            return client.create_stack(
                StackName=prefixed_stack_name,
                TemplateBody=template_body,
                Parameters=params,
                Capabilities=['CAPABILITY_NAMED_IAM'],
            )
        waiter_name = "stack_create_complete"
        act = True
    elif not exists and verb == constants.DOWN_VERB:
        # already deleted
        logger.info(constants.MSG_UP_TO_DATE)
    else:
        raise RuntimeError(f"bad arguments in run_cloudformation - exists:{exists} verb:{verb}")

    if act:
        logger.debug(
            f"cloudformation stack:{prefixed_stack_name} file: {cloudformation_file}"
        )

        # do the deed...
        try:
            with Halo(text=f"Cloudformation {cloudformation_file}", spinner='dots'):
                response = ensure_fn()
                logger.debug(f"response: {response}")

                # ...wait for the result
                waiter = client.get_waiter(waiter_name)
                waiter.wait(
                    StackName=prefixed_stack_name,
                )

        # boto3 exceptions...
        # https://github.com/boto/botocore/blob/develop/botocore/exceptions.py
        except botocore.exceptions.ClientError as e:
            logger.debug(f"boto/client exception: {e}")
            if re.search(ERROR_UP_TO_DATE, str(e), flags=re.IGNORECASE):
                logger.info(constants.MSG_UP_TO_DATE)
            else:
                # no idea
                raise e
        except botocore.exceptions.WaiterError as e:
            logger.debug(f"botocore/waiter exception: {e}")
            if re.search(ERROR_AWS, str(e), flags=re.IGNORECASE):
                raise RuntimeError(f"cloudformation failed - check stack {prefixed_stack_name} in the AWS console")
            else:
                # no idea
                raise e

    # ...If we're still here our stack is up, grab all the cloudformation
    # outputs and add them to the databag
    if verb == constants.DOWN_VERB:
        intermediate_data = {}
    else:
        intermediate_data = cloudformation_outputs(stack_name, prefixed_stack_name, data)

    return intermediate_data


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