import re
import subprocess
import os
import json
from loguru import logger
import boto3
import snakecase
import pathlib
import ringmaster.util as util
from ringmaster import constants as constants
from cfn_tools import load_yaml, dump_yaml
import botocore.exceptions
from halo import Halo
import urllib
import yaml
from ringmaster.util import flatten_nested_dict

RECOMMENDED_EKSCTL_VERSION="0.31.0-rc.1"

# AWS/boto3 API error messages to look for. Use partial regex to protect
# against upstream changes as much as we can
ERROR_UP_TO_DATE = r"No updates are to be performed"
ERROR_AWS = r"encountered a terminal failure state"
ERROR_MISSING = r"does not exist"
ERROR_NO_SUCH_ENTITY = r"NoSuchEntity"


def aws_init():
    # copy files in res/aws to project dir
    if os.path.exists(os.path.expanduser(constants.AWS_USER_TEMPLATE_DIR)):
        source_dir = os.path.expanduser(constants.AWS_USER_TEMPLATE_DIR)
    else:
        source_dir = os.path.join(
            os.path.dirname(
                os.path.realpath(__file__)
            ),
            constants.AWS_TEMPLATE_DIR
        )
    logger.info(f"installing templates from {source_dir}...")

    # shutils.copytree doesnt work until python 3.8 as need to overwrite dest
    # TIL: https://askubuntu.com/a/86891/594199
    util.run_cmd(["cp", "-a", f"{source_dir}/.", "."])

# databag:
#   + cluster_vpc_cidr
#   + cluster_private_subnets
#   + cluster_private_subnet_{n}
#   + cluster_public_subnets
#   + cluster_public_subnet_{n}
def do_eks_cluster_info(filename, verb, data):
    sanity_check(data)
    logger.info(f"eks cluster info: {filename}")
    ec2 = boto3.client('ec2', region_name=data["aws_region"])
    try:

        # VPC CIDR block
        response = ec2.describe_vpcs(
            Filters=[{
                'Name': 'vpc-id',
                'Values': [data['resourcesvpcconfig_vpcid']]
            }]
        )
        vpc_cidr_value = response["Vpcs"][0]["CidrBlock"]
        data["cluster_vpc_cidr"] = vpc_cidr_value

        # subnets
        response = ec2.describe_subnets(
            Filters=[{
                'Name': 'vpc-id',
                'Values': [data['resourcesvpcconfig_vpcid']]
            }]
        )

        private_subnets = list(filter(lambda x: x["MapPublicIpOnLaunch"], response["Subnets"]))
        private_subnet_ids = list(map(lambda x: x["SubnetId"], private_subnets))
        public_subnets = list(filter(lambda x: not x["MapPublicIpOnLaunch"], response["Subnets"]))
        public_subnet_ids = list(map(lambda x: x["SubnetId"], public_subnets))
        # join on whitespace - default separator for bash and python
        data["cluster_private_subnets"] = private_subnet_ids
        data["cluster_public_subnets"] = public_subnet_ids

        # flattened subnet ids for cloudformation/bash
        for i, value in enumerate(private_subnet_ids):
            data[f"cluster_private_subnet{i}"] = value

        for i, value in enumerate(public_subnet_ids):
            data[f"cluster_public_subnet{i}"] = value

    except KeyError as e:
        raise RuntimeError(
            f"missing required field in in databag: {e} - EKS cluster created yet?"
        )
    except IndexError as e:
        raise RuntimeError(
            f"No data returned for this EKS cluster: {e} - EKS cluster created yet?"
        )


def filename_to_stack_name(cloudformation_file):
    return os.path.basename(cloudformation_file)\
        .replace(constants.PATTERN_LOCAL_CLOUDFORMATION_FILE, "")\
        .replace(".yaml", "")


def load_eksctl_databag(data):
    eksctl_databag_file = data[constants.KEY_EKSCTL_DATABAG]
    if os.path.getsize(eksctl_databag_file):
        logger.debug(f"loading eksctl cluster info from from {eksctl_databag_file}")
        with open(eksctl_databag_file) as json_file:
            # strip outer array
            extra_data = json.load(json_file)[0]

        flattened_extra_data = flatten_nested_dict(extra_data)
        logger.debug(f"loaded items:{len(flattened_extra_data)} data:{flattened_extra_data}")
        data.update(flattened_extra_data)

        # empty the bag so we know to ignore it
        open(eksctl_databag_file, 'w').close()


def cloudformation_param(key, value):
    return {
        "ParameterKey": key,
        "ParameterValue": value
    }


def stack_params(filename, data):
    # we can only insert stack parameters that are defined in YAML or cfn
    # will barf, so grab the parameter names from the CFN file and then
    # grab the corresponding parameters from the databag. If anything is
    # missing bomb out now before CFN does.
    # parse with cfn_flip as pyyaml cant handle things like `!Ref`
    # https://stackoverflow.com/a/55349491/3441106
    logger.debug(f"reading cloudformation parameters from {filename}")
    parsed = load_yaml(pathlib.Path(filename).read_text())

    params = []

    if "Parameters" in parsed:
        for cfn_param in parsed["Parameters"]:
            logger.debug(f"processing parameter: {cfn_param}")

            snakecase_param = util.string_to_snakecase(cfn_param)
            if data.get(cfn_param):
                value = data.get(cfn_param)
                logger.debug(f"{cfn_param} set to {value}")
                params.append(cloudformation_param(cfn_param, value))
            elif data.get(snakecase_param):
                value = data.get(snakecase_param)
                logger.debug(f"{cfn_param} set to {value}")
                params.append(cloudformation_param(cfn_param, value))
            elif "Default" in parsed["Parameters"][cfn_param]:
                # cloudformation allows the empty string as a default
                logger.debug(f"Using cloudformation default for {cfn_param}")
            else:
                raise RuntimeError(
                    f"Cloudformation file:{filename} missing param:{cfn_param} "
                        f"expected databag:{snakecase_param}, avaiable:{data.keys()}"
                )
    else:
        logger.debug(f"no Parameters section in {filename}")

    return params


def stack_exists(client, stack_name):
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


def cloudformation_outputs(client, stack_name, prefixed_stack_name, data):
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
            key_name = output["ExportName"].replace(f"{prefixed_stack_name}-", f"{stack_name}-")
            key_name = util.string_to_snakecase(key_name)

            string_value = str(output["OutputValue"])
            intermediate_databag[key_name] = string_value

    logger.debug(f"cloudformation - outputs:{len(intermediate_databag)} value: {intermediate_databag}")
    data.update(intermediate_databag)


# Cloudformation has a hard 51200 byte max file size. To work around this
# files must be hosted on S3. This is an issue with the AWS best
# practice/quickstart files...
def do_remote_cloudformation(filename, verb, data):
    # local file contains a link to the S3 hosted cloudformation
    with open(filename) as f:
        config = yaml.safe_load(f)

    remote = config["remote"]
    local_file = os.path.join(os.path.dirname(filename), config["local_file"])

    # download the remote file so that:
    #   a) we can look at it
    #   b) we have a record of what was deployed
    #   c) we can grab the parameter list
    # download a fresh copy every time since cloudformation will...
    logger.debug(f"download {remote} to {local_file}")
    util.download(remote, local_file)
    stack_name = filename_to_stack_name(local_file)
    cloudformation(stack_name, local_file, verb, data, template_url=remote)


def do_local_cloudformation(filename, verb, data):
    logger.info(f"cloudformation {filename}")
    template_body = pathlib.Path(filename).read_text()
    stack_name = filename_to_stack_name(filename)

    cloudformation(stack_name, filename, verb, data, template_body=template_body)


def cloudformation(stack_name, filename, verb, data, template_body=None, template_url=None):
    sanity_check(data)

    prefixed_stack_name = f"{data['name']}-{stack_name}"
    params = stack_params(filename, data)
    client = boto3.client('cloudformation', region_name=data["aws_region"])
    exists = stack_exists(client, prefixed_stack_name)

    if template_body:
        template_source = {
            "TemplateBody": template_body,
        }
    elif template_url:
        template_source = {
            "TemplateURL": template_url
        }
    else:
        raise RuntimeError(
            "cloudformation - missing both TemplateBody and TemplateURL"
        )

    act = False

    if exists and verb == constants.UP_VERB:
        # update
        def ensure_fn():
            return client.update_stack(
                StackName=prefixed_stack_name,
                Parameters=params,
                Capabilities=['CAPABILITY_NAMED_IAM'],
                **template_source
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
                Parameters=params,
                Capabilities=['CAPABILITY_NAMED_IAM'],
                **template_source
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
            f"cloudformation stack:{prefixed_stack_name} file: {stack_name}"
        )

        # do the deed...
        try:
            with Halo(text=f"Cloudformation {stack_name}", spinner='dots'):
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
    if verb != constants.DOWN_VERB:
        cloudformation_outputs(client, stack_name, prefixed_stack_name, data)


def do_iam(filename, verb, data):
    logger.info(f"AWS IAM: {filename}")

    basename = os.path.basename(filename)
    policy_name = basename[:-len(constants.PATTERN_AWS_IAM_POLICY)]
    policy_arn = f"arn:aws:iam::{data['aws_account_id']}:policy/{policy_name}"
    client = boto3.client('iam', region_name=data["aws_region"])

    try:
        policy_exists = client.get_policy(PolicyArn=policy_arn)
    except botocore.exceptions.ClientError as e:
        logger.debug(f"AWS IAM - exception: {e}")
        if re.search(ERROR_NO_SUCH_ENTITY, str(e), re.IGNORECASE):
            policy_exists = False
        else:
            raise e

    if verb == constants.UP_VERB and policy_exists:
        logger.info(constants.MSG_UP_TO_DATE)
    elif verb == constants.UP_VERB and not policy_exists:
        logger.debug(f"creating IAM policy:{policy_name} file:{filename}")
        with open(filename, 'r') as f:
            file_content = f.read()
        response = client.create_policy(
            PolicyName=policy_name,
            PolicyDocument=file_content,
        )
        logger.debug(f"...result: {response}")
        databag_key = ("aws_iam_" + policy_name).lower()
        extra_data = {databag_key: policy_arn}
        data.update(extra_data)
    elif verb == constants.DOWN_VERB and policy_exists:
        logger.debug(f"deleting IAM policy:{policy_name}")
        response = client.delete_policy(
            PolicyArn=policy_arn
        )
        logger.debug(f"...result: {response}")
    elif verb == constants.DOWN_VERB and not policy_exists:
        logger.info(constants.MSG_UP_TO_DATE)
    else:
        raise RuntimeError(f"AWS IAM - invalid verb {verb}")


def sanity_check(data):
    if not data.get("aws_region"):
        raise RuntimeError("must set aws_region in databag")
    if not data.get("aws_account_id"):
        raise RuntimeError("must set aws_account_id in databag")

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