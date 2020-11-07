import os
UP_VERB = "up"
DOWN_VERB = "down"
DATABAG_FILE = "databag.yaml"
RES_DIR = "res"
RES_KUSTOMIZER_DIR = os.path.join(RES_DIR, "kustomizer")
RES_AWS_DIR = os.path.join(RES_DIR, "aws")
RES_AWS_IAM_DIR = os.path.join(RES_AWS_DIR, "iam")
RES_KUSTOMIZER_RKUBELOG_DIR = os.path.join(RES_KUSTOMIZER_DIR, "rkubelog")
RINGMASTER_ENV = {
    "res_dir": RES_DIR,
    "res_kustomizer": RES_KUSTOMIZER_DIR,
    "res_aws_dir": RES_AWS_DIR,
    "res_aws_iam_dir": RES_AWS_IAM_DIR,
    "res_kustomizer_rkubelog_dir": RES_KUSTOMIZER_RKUBELOG_DIR,
}
PATTERN_CLOUDFORMATION_FILE = ".cloudformation.yaml"
PATTERN_BASH = ".sh"
PATTERN_KUBECTL_FILE = ".kubectl.yaml"
PATTERN_SOLARWINDS_PAPERTRAIL_FILE = "solarwinds_papertrail.yaml"
MSG_UP_TO_DATE = "[√] up to date"
SUBSTITUTE_VARIABLE_REGEX = r"(\$\{\w+\})"
KUSTOMIZATION_FILE = "kustomization.yaml"