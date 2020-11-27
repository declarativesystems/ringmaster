import tempfile
import os
import yaml
import shutil
from loguru import logger
import json
from .util import run_cmd
from pathlib import Path
from ringmaster import constants
import ringmaster.util as util
import subprocess


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





def run_kubectl(verb, flag, path, data):
    if data is None:
        data = {}

    if verb == constants.UP_VERB:
        kubectl_cmd = "apply"
    elif verb == constants.DOWN_VERB:
        kubectl_cmd = "delete"
    else:
        raise ValueError(f"invalid verb: {verb}")

    # --force is to recreate any immutable resources we touched
    cmd = ["kubectl", kubectl_cmd, "--force", flag, path]
    if data.get("debug"):
        cmd.append("-v=2")
    run_cmd(cmd, data)


def delete_k8s_secret(secret_namespace, secret_name):
    try:
        run_cmd(["kubectl", "delete", "secret", "-n", secret_namespace, secret_name])
    except RuntimeError as e:
        logger.error(f"delete k8s secret failed - moving on: {e}")


def register_k8s_secret(secret_namespace, secret_name, data):
    logger.debug(f"registering k8s secret:{secret_name}")
    secret_data = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "namespace": secret_namespace,
            "name": secret_name,
        },
        "data": {}
    }

    # each member of data needs to have its value base64 encoded
    for k, v in data.items():
        secret_data["data"][k] = util.base64encode(v)

    # secret completed - save it somewhere, kubectl, delete
    _, secret_file = tempfile.mkstemp(suffix=".yaml", prefix="ringmaster")
    with open(secret_file, 'w') as outfile:
        yaml.dump(secret_data, outfile)

    logger.debug("creating secret with kubectl")

    run_kubectl(constants.UP_VERB, "-f", secret_file, data)
    os.unlink(secret_file)


def do_kubectl(filename, verb, data=None):
    # substitute ${...} variables from databag, bomb out if any missing
    logger.info(f"kubectl: {filename}")
    processed_file = util.substitute_placeholders_in_file(filename, "#", data)
    logger.debug(f"kubectl processed file: {processed_file}")

    try:
        run_kubectl(verb, "-f", processed_file, data)
    except RuntimeError as e:
        if verb == constants.DOWN_VERB:
            logger.error(f"kubectl error - moving on: {e}")
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
    processed_filename = util.substitute_placeholders_in_file(filename, "#", data)
    with open(processed_filename) as f:
        config = yaml.safe_load(f)

    # if there is an adjacent `values.yaml` file, process it for substitutions and use it
    values_yaml = os.path.join(os.path.dirname(filename), "values.yaml")
    if os.path.exists(values_yaml):
        processed_values_file = util.substitute_placeholders_in_file(values_yaml, "#", data)
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

    # step 1 - process all substitutions
    yaml_string = util.substitute_placeholders_in_memory(filename, data)

    # step 2 - load yaml
    first = True
    data = None
    for record in yaml.safe_load_all(yaml_string):
        if first:
            # step 3 - load first record which is is the k8s secret template
            data = record

            # create the `data` key if needed
            if not data.get("data"):
                data["data"] = {}
            first = False
            logger.debug(f"secret_kubectl - processed first record of {filename}")
        elif verb == constants.UP_VERB:
            # step 4 - 2nd record is data field to add to `data` all secrets
            # were already inserted in the substitute placeholders phase so
            # just need to base64 encode it
            # This is only done in UP mode - if we are going down the value
            # of the secret doesnt matter
            secret_data = record.get("data")
            if secret_data:
                for k, v in record["data"].items():
                    logger.debug(f"secret_kubectl - adding data field:{k} ")
                    data["data"][k] = util.base64encode(v)
                logger.debug(f"secret_kubectl - processed subsequent record of {filename}")
            else:
                raise RuntimeError(f"secret_kubectl - Non-first document missing key `data` filename:${filename}")

    # step 5 - secret completed - save it somewhere, kubectl, delete
    _, secret_file = tempfile.mkstemp(suffix=".yaml", prefix="ringmaster")
    with open(secret_file, 'w') as outfile:
        yaml.dump(data, outfile)

    logger.debug("secret_kubectl - creating secret with kubectl")
    logger.info(f"secret: {data}")

    run_kubectl(verb, "-f", secret_file, data)
    os.unlink(secret_file)