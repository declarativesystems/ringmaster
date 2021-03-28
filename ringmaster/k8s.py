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
import tempfile
import os
import yaml
import shutil
from loguru import logger
from .util import run_cmd
from pathlib import Path
from ringmaster import constants
import ringmaster.util as util
import re

def copy_kustomization_files(root_dir, target_dir):

    kustomization_file = os.path.join(root_dir, constants.PATTERN_KUSTOMIZATION_FILE)
    with open(kustomization_file) as f:
        kustomization_data = yaml.safe_load(f)

    # kustomization.yaml
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        kustomization_file, os.path.join(target_dir, constants.PATTERN_KUSTOMIZATION_FILE))
    # resources
    for resource_file in kustomization_data.get("resources", []):
        source_file = os.path.join(root_dir, resource_file)
        dest_file = os.path.join(target_dir, resource_file)
        dest_dir = os.path.dirname(dest_file)
        logger.debug(f"mkdir {dest_dir}")
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"saving kustomizer resource: {dest_file}")
        logger.debug(f"copy {source_file} {dest_file}")
        shutil.copyfile(source_file, dest_file)

    # bases
    for base_res in kustomization_data.get("bases", []):
        source_dir = os.path.join(root_dir, base_res)
        dest_dir = os.path.join(target_dir, base_res)

        # use copy - older python copytree cant copy files that exist in the
        # destination
        logger.debug(f"rmtree {dest_dir}")
        shutil.rmtree(dest_dir, ignore_errors=True)
        logger.debug(f"copytree {source_dir} {dest_dir}")
        shutil.copytree(source_dir, dest_dir)

    # patches
    for patch in kustomization_data.get("patchesJSON6902"):
        patch_file = patch["path"]
        source_file = os.path.join(root_dir, patch_file)
        dest_file = os.path.join(target_dir, patch_file)
        logger.debug(f"copy {source_file} {dest_file}")
        shutil.copy(source_file, dest_file)

def check_kubectl_session():
    """check kubectl connected to cluster before running commands"""
    try:
        run_cmd("kubectl config current-context")
        connected = True
    except RuntimeError:
        connected = False
    return connected


def run_kubectl(verb, flag, path, data):
    if data is None:
        data = {}

    if verb == constants.UP_VERB:
        kubectl_cmd = "apply"
    elif verb == constants.DOWN_VERB:
        kubectl_cmd = "delete"
    else:
        raise ValueError(f"invalid verb: {verb}")

    if check_kubectl_session():
        # --force is to recreate any immutable resources we touched
        cmd = ["kubectl", kubectl_cmd, "--force", flag, path]
        if data.get("debug"):
            cmd.append("-v=2")

        try:
            run_cmd(cmd, data)
        except RuntimeError as e:
            if verb == constants.DOWN_VERB:
                logger.warning("Error running kubectl but system is going down - ignoring")
            else:
                raise e
    elif verb == constants.DOWN_VERB:
        logger.warning("kubectl has no current context but system is going down - ignoring")
    else:
        raise RuntimeError("kubectl not logged in - context is not set")


def do_kubectl(filename, verb, data=None):
    # substitute ${...} variables from databag, bomb out if any missing
    logger.info(f"kubectl: {filename}")

    try:
        processed_file = util.substitute_placeholders_from_file_to_file(filename, "#", verb, data)
        logger.debug(f"kubectl processed file: {processed_file}")

        run_kubectl(verb, "-f", processed_file, data)
    except RuntimeError as e:
        if verb == constants.DOWN_VERB:
            logger.warning(f"kubectl error - moving on: {e}")
        else:
            raise e
    except KeyError as e:
        if verb == constants.DOWN_VERB:
            logger.warning(f"missing key - moving on: {e}")
        else:
            raise e


def do_kustomizer(filename, verb, data=None):
    logger.info(f"kustomizer: {filename}")
    sources_dir = os.path.dirname(filename)
    try:
        run_kubectl(verb, "-k", sources_dir, data)
    except RuntimeError as e:
        if verb == constants.DOWN_VERB:
            logger.error(f"kustomizer error - moving on: {e}")
        else:
            raise e


def helm_repos(base_cmd, config, filename):
    repos_list = util.run_cmd_json(base_cmd + ["repo", "list", "--output", "json"])
    logger.debug(f"helm repos installed: {repos_list}")
    repos_installed = list(map(lambda x: x["name"], repos_list))
    logger.debug(f"helm repos installed: {repos_installed}")

    repos = config.get("repos", {})
    if repos:
        for repo_key, source in config.get("repos", {}).items():
            logger.debug(f"helm - request install repo:{repo_key}")
            if repo_key not in repos_installed:
                logger.info(f"helm - installing repo:{repo_key}")
                cmd = base_cmd + ["repo", "add", repo_key, source]
                util.run_cmd(cmd)
    else:
        logger.warning(f"helm - no helm repos specified in {filename}")


def do_helm(filename, verb, data=None):
    logger.info(f"helm: {filename}")

    # settings for helm...
    processed_filename = util.substitute_placeholders_from_file_to_file(filename, "#", verb, data)
    with open(processed_filename) as f:
        config = yaml.safe_load(f)

    # if there is an adjacent `values.yaml` file, process it for substitutions and use it
    values_yaml = os.path.join(os.path.dirname(filename), "values.yaml")
    if os.path.exists(values_yaml):
        processed_values_file = util.substitute_placeholders_from_file_to_file(values_yaml, "#", verb, data)
        logger.debug(f"helm - values: {processed_values_file}")
    else:
        processed_values_file = False

    if verb == constants.UP_VERB:
        helm_command = "install"
    elif verb == constants.DOWN_VERB:
        helm_command = "uninstall"
    else:
        raise RuntimeError(f"helm - invalid verb: {verb}")

    base_cmd = ["helm"]
    if data.get("debug"):
        base_cmd.append("--debug")

    if config.get("namespace"):
        namespace = config['namespace']
        logger.debug(f"using namespace {namespace}")
        base_cmd.append("-n")
        base_cmd.append(namespace)

    try:
        # helm repos...
        if verb == constants.UP_VERB:
            helm_repos(base_cmd, config, filename)

        # helm deployments
        helm_list = util.run_cmd_json(base_cmd + ["list", "--output", "json"])
        helm_deployments = list(map(lambda x: x["name"], helm_list))
        logger.debug(f"helm deployments installed: {helm_deployments}")
        exists = config["name"] in helm_deployments
        if (verb == constants.UP_VERB and exists) or (verb == constants.DOWN_VERB and not exists):
            logger.info(f"helm - already installed:{config['name']}")
        elif (verb == constants.UP_VERB and not exists) or (verb == constants.DOWN_VERB and exists):
            logger.info(f"helm - {helm_command}:{config['name']}")
            cmd = base_cmd + [helm_command, config["name"]]
            if verb == constants.UP_VERB:
                cmd.append(config["install"])
                if processed_values_file:
                    cmd.append("--values")
                    cmd.append(processed_values_file)
                else:
                    for setting in config.get("set", []):
                        cmd.append("--set")
                        cmd.append(setting)
                cmd += config.get("options", [])
                version = config.get("version")
                if version:
                    cmd += ["--version", version]
                else:
                    logger.warning(f"recommending versioning helm chart in {filename}")
                cmd += config.get("options", [])
            util.run_cmd(["helm", "repo", "update"])
            util.run_cmd(cmd)
        else:
            raise RuntimeError(f"helm - invalid verb {verb}")

    except KeyError as e:
        raise RuntimeError(f"helm - {filename} missing key: {e}")
    except RuntimeError as e:
        if verb == constants.DOWN_VERB:
            logger.error(f"helm - error running helm, moving on: {e}")
        else:
            raise e

def do_secret_kubectl(filename, verb, data):
    """create or delete a secret from a kubectl template file. This results in
    calling the k8s api directly - no processed file (which would contain the
    secret...) is created

    The input yaml file must be formatted like this:

    ---
    apiVersion: v1
    kind: Secret
    metadata:
      name: ...
    ---
    data:
        keyname: value (we will base64 encode it for you)
    """
    logger.info(f"secret_kubectl: {filename}")

    # step 1 - read entire file into memory and split on yaml record separator
    # `---` make sure we have exactly 2 records
    with open(filename) as f:
        file_contents = f.read()

    records = re.split(r'\s*---\s*', file_contents)


    # step 2 - process all substitutions in first document (metadata)
    # since yaml lets the file start with `---` its possible to end up
    # with a 'blank' first record so skip until we find something
    yaml_data = False
    while not yaml_data:
        yaml_string_metadata = util.substitute_placeholders_from_memory_to_memory(records[0], verb, data)

        # step 3 - convert string to yaml data structure - this will be merged
        # with the looked-up data from record 2 to build the entire secret
        yaml_data = yaml.safe_load(yaml_string_metadata)

        if not yaml_data:
            # skip this blank record and try again...
            records.pop(0)

    record_count = len(records)
    if record_count == 2:
        # secret file in correct format

        # step 4 - record 2 contains the secret data to add - if we are upping
        # substitute in the real values
        if verb == constants.UP_VERB:
            # substitute function expects list of strings...
            yaml_string_secret = util.substitute_placeholders_from_memory_to_memory(records[1], verb, data)
            logger.debug(f"raw secret data after placeholder substitution: {yaml_string_secret}")
            yaml_data_secret = yaml.safe_load(yaml_string_secret)

            # parsed yaml must contain `data` key...
            secret_data = yaml_data_secret.get("data")
            if secret_data:
                # create the `data` key in the overall structure if needed
                if not yaml_data.get("data"):
                    yaml_data["data"] = {}

                # base 64 encode each field and add it to the yaml secret
                for k, v in secret_data.items():
                    logger.debug(f"secret_kubectl - adding data field:{k} ")
                    yaml_data["data"][k] = util.base64encode(v)
            else:
                raise RuntimeError(f"secret_kubectl - record 2 missing key `data` filename:${filename}")

        else:
            # Add dummy section to keep kubectl from complaining
            yaml_data["data"] = {}

        # step 5 - secret completed - save it somewhere, kubectl, delete
        _, secret_file = tempfile.mkstemp(suffix=".yaml", prefix="ringmaster")
        with open(secret_file, 'w') as outfile:
            yaml.dump(yaml_data, outfile)

        logger.debug("secret_kubectl - creating secret with kubectl")

        # print the entire secret for debug purposes ;-)
        logger.debug(f"secret: {yaml_data}")

        run_kubectl(verb, "-f", secret_file, data)
        os.unlink(secret_file)
    else:
        raise RuntimeError(f"secret_kubectl - ${filename} must contain exactly 2 documents, found:{record_count}")