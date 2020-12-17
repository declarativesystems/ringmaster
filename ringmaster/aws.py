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


def route_table_for_subnet(ec2, subnet_id):
    # get the route tables
    logger.debug(f"looking describe_route_table subnet_id:{subnet_id}")
    response = ec2.describe_route_tables(
        Filters=[{
            'Name': 'association.subnet-id',
            'Values': [subnet_id]
        }]
    )
    try:
        logger.debug(f"...result: {response}")
        route_table_id = response["RouteTables"][0]["RouteTableId"]
    except KeyError as e:
        logger.warn(f"aws - no RouteTableId found for subnet {subnet_id} - associated?")
        route_table_id = None

    return route_table_id


def eks_cluster_info(aws_region, cluster_name, data):
    sanity_check(data)

    # eksctl cluster info --> databag
    logger.debug("eks cluster info")
    eksctl_data = util.run_cmd_json(
        ["eksctl", "get", "cluster", "--region", aws_region, cluster_name, "--output", "json"],
        data
    )

    flattened_eksctl_data = flatten_nested_dict(eksctl_data)
    logger.debug(f"loaded items:{len(flattened_eksctl_data)} data:{flattened_eksctl_data}")
    data.update(flattened_eksctl_data)

    #   + cluster_vpc_cidr
    #   + cluster_private_subnets
    #   + cluster_private_subnet_{n}
    #   + cluster_private_route_tables
    #   + cluster_private_route_table_{n}
    #   + cluster_public_subnets
    #   + cluster_public_subnet_{n}
    #   + cluster_public_route_tables
    #   + cluster_public_route_table_{n}
    ec2 = boto3.client('ec2', region_name=aws_region)
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

        #   + cluster_public_route_tables
        #   + cluster_public_route_table_{n}
        data["cluster_public_route_tables"] = []
        for i, value in enumerate(public_subnet_ids):
            route_table_id = route_table_for_subnet(ec2, public_subnet_ids[i])
            data["cluster_public_route_tables"].append(route_table_id)
            data[f"cluster_public_route_table{i+1}"] = route_table_id

        #   + cluster_private_route_tables
        #   + cluster_private_route_table_{n}
        data["cluster_private_route_tables"] = []
        for i, value in enumerate(private_subnet_ids):
            route_table_id = route_table_for_subnet(ec2, private_subnet_ids[i])
            data["cluster_private_route_tables"].append(route_table_id)
            data[f"cluster_private_route_table{i+1}"] = route_table_id


        # flattened subnet ids for cloudformation/bash
        for i, value in enumerate(private_subnet_ids):
            data[f"cluster_private_subnet{i+1}"] = value

        for i, value in enumerate(public_subnet_ids):
            data[f"cluster_public_subnet{i+1}"] = value

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
                raise KeyError(
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

    try:
        cloudformation(stack_name, filename, verb, data, template_body=template_body)
    except KeyError as e:
        if verb == constants.DOWN_VERB:
            logger.warning(f"missing values prevent running cloudformation - skipping as system going down: {e}")
        else:
            raise e


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


def do_iam_policy(filename, verb, data):
    logger.info(f"AWS IAM policy: {filename}")

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
    elif verb == constants.DOWN_VERB and policy_exists:
        logger.debug(f"delete all versions of IAM policy:{policy_name}...")
        # delete all versions of the policy and then the policy itself
        response = client.list_policy_versions(PolicyArn=policy_arn)

        for version_info in response["Versions"]:
            if not version_info["IsDefaultVersion"]:
                version_id = version_info["VersionId"]
                logger.debug(f"deleting IAM policy:{policy_arn} version:{version_id}...")
                response = client.delete_policy_version(
                    PolicyArn=policy_arn,
                    VersionId=version_id,
                )
                logger.debug(f"...result: {response}")

        logger.debug(f"deleting overall IAM policy:{policy_name}...")
        try:
            response = client.delete_policy(
                PolicyArn=policy_arn
            )
            logger.debug(f"...result: {response}")
        except botocore.exceptions.ClientError as e:
            if verb == constants.DOWN_VERB:
                logger.warning(f"Error deleting policy:{policy_arn} - continuing as system is going down")
            else:
                raise e
    elif verb == constants.DOWN_VERB and not policy_exists:
        logger.info(constants.MSG_UP_TO_DATE)
    else:
        raise RuntimeError(f"AWS IAM - invalid verb {verb}")

    if verb == constants.UP_VERB:
        databag_key = ("aws_iam_policy_" + snakecase.convert(policy_name))
        extra_data = {databag_key: policy_arn}
        logger.debug(f"added to databag:{databag_key}")
        data.update(extra_data)


def do_iam_role(filename, verb, data):
    logger.info(f"AWS IAM role: {filename}")

    basename = os.path.basename(filename)
    name = basename[:-len(constants.PATTERN_AWS_IAM_ROLE)]
    arn = f"arn:aws:iam::{data['aws_account_id']}:policy/{name}"
    client = boto3.client('iam', region_name=data["aws_region"])

    try:
        exists = client.get_role(RoleName=name)
    except botocore.exceptions.ClientError as e:
        logger.debug(f"AWS IAM - exception: {e}")
        if re.search(ERROR_NO_SUCH_ENTITY, str(e), re.IGNORECASE):
            exists = False
        else:
            raise e

    if verb == constants.UP_VERB and exists:
        logger.info(constants.MSG_UP_TO_DATE)
    elif verb == constants.UP_VERB and not exists:
        logger.debug(f"creating IAM role:{name} file:{filename}")
        with open(filename, 'r') as f:
            file_content = f.read()
        response = client.create_role(
            RoleName=name,
            AssumeRolePolicyDocument=file_content,
        )
        logger.debug(f"...result: {response}")
    elif verb == constants.DOWN_VERB and exists:
        logger.debug(f"deleting IAM policy:{name}")
        response = client.delete_role(
            RoleName=name
        )
        logger.debug(f"...result: {response}")
    elif verb == constants.DOWN_VERB and not exists:
        logger.info(constants.MSG_UP_TO_DATE)
    else:
        raise RuntimeError(f"AWS IAM - invalid verb {verb}")

    if verb == constants.UP_VERB:
        databag_key = ("aws_iam_role_" + snakecase.convert(name))
        extra_data = {databag_key: name}
        logger.debug(f"added to databag:{databag_key}")
        data.update(extra_data)


def sanity_check(data):
    if not data.get("aws_region"):
        raise RuntimeError("must set aws_region in databag")
    if not data.get("aws_account_id"):
        raise RuntimeError("must set aws_account_id in databag")


def secret_exists(client, secret_id):
    try:
        response = client.describe_secret(
            SecretId=secret_id
        )
        exists = True
        deleted = True if response.get("DeletedDate") else False
    except botocore.exceptions.ClientError as e:
        logger.error(f"--> {e}")
        exists = False
        deleted = False
    logger.debug(f"secret_id:{secret_id} exists:{exists}")
    return exists, deleted


def update_secret(client, secret_id, secret_value, deleted):
    if deleted:
        logger.debug(f"Restoring deleted secret: {secret_id}")
        response = client.restore_secret(
            SecretId=secret_id
        )

    response = client.update_secret(
        SecretId=secret_id,
        SecretString=secret_value
    )
    logger.info(f"created secret id:{secret_id} ARN:{response}")


def create_secret(client, secret_id, secret_value):
    response = client.create_secret(
        Name=secret_id,
        SecretString=secret_value
    )
    logger.info(f"created secret id:{secret_id} ARN:{response}")


def delete_secret(client, secret_id):
    exists, deleted = secret_exists(client, secret_id)
    if exists and not deleted:
        response = client.delete_secret(
            SecretId=secret_id
        )
        logger.debug(f"secret id:{secret_id} deleted:{response}")
    else:
        logger.debug(f"secret id:{secret_id} does not exist, moving on")


# `secret_id` - The identifier of the secret whose details you want to
# retrieve. You can specify either the Amazon Resource Name (ARN) or the
# friendly name of the secret.
def do_secrets_manager(filename, verb, data):
    logger.info(f"secretsmanager: {filename}")
    processed_file = util.substitute_placeholders_from_file_to_file(filename, "#", verb, data)
    with open(processed_file) as f:
        config = yaml.safe_load(f)

    client = boto3.client('secretsmanager', region_name=data["aws_region"])

    for secret in config.get("secrets", []):
        exists, deleted = secret_exists(client, secret["name"])
        if verb == constants.UP_VERB and exists:
            update_secret(client, secret["name"], secret["value"], deleted)
        elif verb == constants.UP_VERB and not exists:
            create_secret(client, secret["name"], secret["value"])
        elif verb == constants.DOWN_VERB and exists:
            delete_secret(client, secret["name"])
        elif verb == constants.DOWN_VERB and not exists:
            logger.debug(f"secretsmanager - already deleted:{secret['name']}")
        else:
            raise RuntimeError(f"secretsmanager - invalid verb: {verb}")

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


def do_eksctl(filename, verb, data):
    logger.info(f"eksctl: ${filename}")
    processed_filename = util.substitute_placeholders_from_file_to_file(filename, "#", verb, data)
    with open(processed_filename) as f:
        config = yaml.safe_load(f)

    # eksctl needs region and cluster name - grab these well-known fields from
    # processed yaml file to avoid needing well-known keys in databag
    try:
        aws_region = config["metadata"]["region"]
        cluster_name = config["metadata"]["name"]
    except KeyError as e:
        raise RuntimeError(f"eksctl file:{filename} missing required value {e}")

    try:
        util.run_cmd(["eksctl", "get", "cluster", "-n", cluster_name, "--region", aws_region], data)
        exists = True
    except RuntimeError as e:
        logger.debug(f"cluster probably doesnt exist: {e}")
        exists = False

    if verb == constants.UP_VERB and exists:
        logger.info(constants.MSG_UP_TO_DATE)
    elif verb == constants.UP_VERB and not exists:
        util.run_cmd(["eksctl", "create", "cluster", "-f", processed_filename], data)
    elif verb == constants.DOWN_VERB and exists:
        util.run_cmd(["eksctl", "delete", "cluster", "-f", processed_filename], data)
    elif verb == constants.DOWN_VERB and not exists:
        logger.info(constants.MSG_UP_TO_DATE)
    else:
        raise RuntimeError(f"eksctl - invalid verb: {verb}")

    if verb == constants.UP_VERB:
        eks_cluster_info(aws_region, cluster_name, data)
