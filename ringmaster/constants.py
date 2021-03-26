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
import os
UP_VERB = "up"
DOWN_VERB = "down"
GET_VERB = "get"
METADATA_VERB = "metadata"
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
PATTERN_SECRET_KUBECTL = ".secret_kubectl.yaml"
PATTERN_CLOUDFLARE = ".cloudflare.yaml"

MSG_UP_TO_DATE = "[√] up to date"
SUBSTITUTE_VARIABLE_REGEX = r"(\$\{[^}]+})"
SINGLE_QUOTED_STRING_REGEX = r"('.*?(?<!\\)')"

KEY_INTERMEDIATE_DATABAG="intermediate_databag_file"

AWS_TEMPLATE_DIR = "res/aws"
AWS_USER_TEMPLATE_DIR = "~/.ringmaster/res/aws"

COMMENT_SQL = "--"
SNOWFLAKE_CLEANUP_FILENAME = "down.snowflake.sql"


CFN_BASE64 = "base64"
ENV_DIR = ".env"
METADATA_FILE = "metadata.yaml"
METADATA_FILES_KEY = "files"
METADATA_NAME_KEY = "name"
METADATA_HASH_KEY = "sha1sum"
SOURCE_KEY = "source"

DEFAULT_DATABAG = {
    "msg_up_to_date": MSG_UP_TO_DATE,
    "up_verb": UP_VERB,
    "down_verb": DOWN_VERB,
}