import boto3
import botocore.exceptions
import re

logger = None

# used for testing - ringmaster inserts updated values
databag = {
    "cluster_name": "cryptoform",
    "resourcesvpcconfig_vpcid": "vpc-004d63153c238d5f1",
    "region": "ap-southeast-2",
    "infra_efs": "fs-8975a7b1",
    "cluster_vpc_cidr": "192.168.0.0/16",
    "cluster_private_subnets": "subnet-0167d289c48aa741d,subnet-053a304c577ad0b94",
    "cluster_private_subnets": "subnet-05ac3daeac6e1fd31,subnet-0c4a939b6336ec8e3",
}

# I guess this is a kinda plugin system - works like this:
# 1. databag gets set
# 2. main() gets called
#
# since its just python, run the script and populate databag ^^^ to test
# without ringmaster


def get_security_group_name():
    return f"{databag['cluster_name']}-efs-sg"


def get_security_group_id(ec2):
    security_group_name = get_security_group_name()

    # check if we are up-to-date...
    logger.debug(f"check security group name: {security_group_name} in vpc: {databag['resourcesvpcconfig_vpcid']}")
    response = ec2.describe_security_groups(
        Filters=[{
            'Name': 'vpc-id',
            'Values': [databag['resourcesvpcconfig_vpcid']]
        },{
            'Name': 'group-name',
            'Values': [security_group_name]
        }],
    )
    return response["SecurityGroups"][0]['GroupId'] if len(response["SecurityGroups"]) else None


def ensure_security_group(ec2):
    security_group_name = get_security_group_name()
    security_group_id = get_security_group_id(ec2)
    if security_group_id:
        logger.info(f"security group {security_group_name} already exists")
    else:
    # except botocore.exceptions.ClientError as e:
    #     if re.search("InvalidGroup.NotFound", str(e), re.IGNORECASE):
        logger.debug(f"creating security group: {security_group_name}")
        # lookup VPC cidr block...
        response = ec2.describe_vpcs(
            Filters=[{
                'Name': 'vpc-id',
                'Values': [databag['resourcesvpcconfig_vpcid']]
            }]
        )
        logger.debug(response)
        vpc_cidr_block = response["Vpcs"][0]["CidrBlock"]

        # create security group...
        logger.debug(f"creating security group {security_group_name}")
        response = ec2.create_security_group(
            GroupName=security_group_name,
            Description=f"Allow access to EFS from EKS Cluster ${databag['cluster_name']}",
            VpcId=databag['resourcesvpcconfig_vpcid']
        )
        security_group_id = response['GroupId']
        data = ec2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[{
                'IpProtocol': 'tcp',
                'FromPort': 2049,
                'ToPort': 2049,
                'IpRanges': [{'CidrIp': vpc_cidr_block}]},
            ]
        )
    return security_group_id


def ensure_mount_target(security_group_id, subnet_id):
    client = boto3.client('efs', region_name=databag["aws_region"])
    response = client.describe_mount_targets(
        FileSystemId=databag["infra_efs"]
    )
    logger.debug(response)
    subnet_mount_target = list(filter(lambda x: x.get("SubnetId") == subnet_id, response["MountTargets"]))
    if len(subnet_mount_target):
        logger.info(f"mount target already exists for subnet {subnet_id}")
    else:
        response = client.create_mount_target(
            FileSystemId=databag["infra_efs"],
            SubnetId=subnet_id,
            SecurityGroups=[
                security_group_id,
            ],
        )
        logger.info(response)


def main():
    ec2 = boto3.client('ec2', region_name=databag["aws_region"])
    security_group_id = ensure_security_group(ec2)
    for subnet_id in databag["cluster_private_subnets"]:
        ensure_mount_target(security_group_id, subnet_id)

    databag["cluster_efs_sg"] = security_group_id
    logger.info("done!")


if __name__ == "__main__":
    from loguru import logger
    main()
