import os
UP_VERB = "up"
DOWN_VERB = "down"
DATABAG_FILE = "databag.yaml"
RES_DIR = "res"
RES_AWS_DIR = os.path.join(RES_DIR, "aws")
RES_AWS_IAM_DIR = os.path.join(RES_AWS_DIR, "iam")
RINGMASTER_ENV = {
    "res_dir": RES_DIR,
    "res_aws_dir": RES_AWS_DIR,
    "res_aws_iam_dir": RES_AWS_IAM_DIR,
}
PATTERN_CLOUDFORMATION_FILE = ".cloudformation.yaml"
PATTERN_BASH = ".sh"

MSG_UP_TO_DATE = "[√] up to date"
