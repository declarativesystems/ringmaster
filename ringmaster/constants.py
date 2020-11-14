import os
UP_VERB = "up"
DOWN_VERB = "down"
DATABAG_FILE = "databag.yaml"
OUTPUT_DATABAG_FILE = f"output_{DATABAG_FILE}"

STACK_DIR = "stack"
USER_DIR = "user"

# if we download files, put them inside this directory so we know to skip
SKIP_DIR = "download"

PATTERN_LOCAL_CLOUDFORMATION_FILE = ".cloudformation.yaml"
PATTERN_REMOTE_CLOUDFORMATION_FILE = ".remote_cloudformation.yaml"
PATTERN_BASH = ".sh"
PATTERN_KUBECTL_FILE = ".kubectl.yaml"
PATTERN_SOLARWINDS_PAPERTRAIL_FILE = "solarwinds_papertrail.yaml"
PATTERN_KUSTOMIZATION_FILE = "kustomization.yaml"
PATTERN_RINGMASTER_PYTHON_FILE = ".ringmaster.py"
PATTERN_SNOWFLAKE_SQL = ".snowflake.sql"
PATTERN_SNOWFLAKE_QUERY = ".snowflake_query.sql"
PATTERN_HELM_DEPLOY = "helm_deploy.yaml"
PATTERN_AWS_IAM_POLICY = ".iam_policy.json"
PATTERN_AWS_IAM_ROLE = ".iam_role.json"
PATTERN_SECRETS_MANAGER = "secretsmanager.yaml"
PATTERN_EKSCTL_CONFIG = ".eksctl.yaml"

MSG_UP_TO_DATE = "[√] up to date"
SUBSTITUTE_VARIABLE_REGEX = r"(\$\{\w+\})"

KEY_INTERMEDIATE_DATABAG="intermediate_databag_file"

AWS_TEMPLATE_DIR = "res/aws"
AWS_USER_TEMPLATE_DIR = "~/.ringmaster/res/aws"

COMMENT_SQL = "--"
SNOWFLAKE_CLEANUP_FILENAME = "down.snowflake.sql"