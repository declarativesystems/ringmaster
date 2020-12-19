import boto3
import botocore.exceptions
from loguru import logger
import ringmaster.constants as constants
import time
from halo import Halo


# used for testing - ringmaster inserts updated values
databag = {
    "cluster_name": "acluster",
    "resourcesvpcconfig_vpcid": "vpc-deadbeaf",
    "region": "ap-southeast-2",
    "infra_efs": "fs-deadbeef",
    "cluster_vpc_cidr": "192.168.0.0/16",
    "cluster_private_subnets": "subnet-1a,subnet-1b",
    "cluster_public_subnets": "subnet-2a,subnet-2b",
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
    vpc_id = databag.get('resourcesvpcconfig_vpcid')
    response = False
    # check if we are up-to-date...
    if vpc_id:
        logger.debug(f"check security group name: {security_group_name} in vpc: {databag.get('resourcesvpcconfig_vpcid')}")
        response = ec2.describe_security_groups(
            Filters=[{
                'Name': 'vpc-id',
                'Values': [databag['resourcesvpcconfig_vpcid']]
            },{
                'Name': 'group-name',
                'Values': [security_group_name]
            }],
        )
    else:
        logger.info("missing resourcesvpcconfig_vpcid - presuming already deleted")

    return response["SecurityGroups"][0]['GroupId'] if response and len(response["SecurityGroups"]) else None


def ensure_security_group(ec2, up):
    security_group_name = get_security_group_name()
    security_group_id = get_security_group_id(ec2)
    exists = security_group_id
    if (exists and up) or (not exists and not up):
        logger.info(f"security group {security_group_name} already exists")
    elif not exists and up:
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
    elif exists and not up:
        logger.debug(f"deleting security group: {security_group_name}")
        ec2.delete_security_group(GroupId=security_group_id)


    return security_group_id


def ensure_mount_target(up, security_group_id, subnet_id):
    client = boto3.client('efs', region_name=databag["aws_region"])
    try:
        response = client.describe_mount_targets(
            FileSystemId=databag["efs_efs"]
        )
        logger.debug(response)
        # results in a list of dict with one entry if mount target exists
        subnet_mount_target = list(filter(lambda x: x.get("SubnetId") == subnet_id, response["MountTargets"]))
        exists = len(subnet_mount_target) == 1
        logger.debug(f"subnet_id:{subnet_id} mount target exists:{exists}")

    except botocore.exceptions.ClientError as e:
        logger.debug(e)
        exists = False


    if (exists and up) or (not exists and not up):
        logger.info(f"mount target already exists for subnet {subnet_id}")
    elif not exists and up:
        logger.info(f"creating mount target for {subnet_id}")
        response = client.create_mount_target(
            FileSystemId=databag["efs_efs"],
            SubnetId=subnet_id,
            SecurityGroups=[
                security_group_id,
            ],
        )
        logger.info(response)
    elif exists and not up:
        # delete each mount target
        mount_targets_for_subnet = list(filter(lambda x: x.get("SubnetId") == subnet_id, response["MountTargets"]))
        logger.debug(f"filtered mountTarget target descriptions for:{subnet_id} = {len(mount_targets_for_subnet)}")
        for mount_target in mount_targets_for_subnet:
            mount_target_id = mount_target['MountTargetId']


            with Halo(text=f"deleting mount target: {mount_target_id}", spinner="dots"):
                response = client.delete_mount_target(
                    MountTargetId=mount_target_id
                )

                # we have to wait for each delete here or deleting the SG will fail
                # there are currently no waiters for EFS so just keep polling to see
                # wait for the mount target to vanish
                deleted_ok = False
                waited = 0

                time_to_wait = 20 # seconds
                while not deleted_ok and waited < 600:
                    time.sleep(time_to_wait)
                    waited += time_to_wait
                    try:
                        response = client.describe_mount_targets(
                            MountTargetId=mount_target_id
                        )
                    except botocore.exceptions.ClientError as e:
                        logger.debug(f"error looking up mount target - its probably deleted: {e}")
                        deleted_ok = True


def main(verb):
    ec2 = boto3.client('ec2', region_name=databag["aws_region"])
    up = verb == constants.UP_VERB
    if up:
        security_group_id = ensure_security_group(ec2, up)
        for subnet_id in databag["cluster_private_subnets"]:
            ensure_mount_target(up, security_group_id, subnet_id)

        databag["cluster_efs_sg"] = security_group_id
    else:
        # must delete items in reverse order when going down
        for subnet_id in databag.get("cluster_private_subnets", {}):
            cluster_efs_sg = databag.get("cluster_efs_sg")
            if cluster_efs_sg:
                ensure_mount_target(up, databag["cluster_efs_sg"], subnet_id)
        ensure_security_group(ec2, up)

    logger.info("done!")


if __name__ == "__main__":
    main(True)
