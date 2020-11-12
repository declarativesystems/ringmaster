import base64
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


def base64encode(string):
    string_bytes = string.encode('ascii')
    base64_bytes = base64.b64encode(string_bytes)
    return base64_bytes.decode('ascii')


def run_kubectl(verb, flag, path, data):
    if data is None:
        data = {}

    if verb == constants.UP_VERB:
        kubectl_cmd = "apply"
    elif verb == constants.DOWN_VERB:
        kubectl_cmd = "delete"
    else:
        raise ValueError(f"invalid verb: {verb}")

    cmd = ["kubectl", kubectl_cmd, flag, path]
    if data.get("debug"):
        cmd.append("-v=2")
    run_cmd(cmd, data)


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
        secret_data["data"][k] = base64encode(v)

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

    run_kubectl(verb, "-f", processed_file, data)


def do_kustomizer(filename, verb, data=None):
    logger.info(f"kustomizer: {filename}")
    sources_dir = os.path.dirname(filename)

    run_kubectl(verb, "-k", sources_dir, data)


def do_helm(filename, verb, data=None):
    with open(filename) as f:
        config = yaml.safe_load(f)

    if verb == constants.UP_VERB:
        helm_command = "install"
    elif verb == constants.DOWN_VERB:
        helm_command = "uninstall"
    else:
        raise RuntimeError(f"helm - invalid verb: {verb}")

    base_cmd = ["helm"]
    if data.get("debug"):
        base_cmd.append("--debug")

    try:
        # helm repos...
        if verb == constants.UP_VERB:
            repos_list = util.run_cmd_json(["helm", "repo", "list", "--output", "json"])
            logger.debug(f"helm repos installed: {repos_list}")
            repos_installed = list(map(lambda x: x["name"], repos_list))
            logger.debug(f"helm repos installed: {repos_installed}")

            repos = config.get("repos", {})
            if repos:
                for repo_key, source in config.get("repos", {}).items():
                    logger.debug(f"helm - request install repo: {repo_key}")
                    if repo_key not in repos_installed:
                        logger.info(f"helm - installing {repo_key}")
                        cmd = base_cmd + ["repo", "add", repo_key, source]
                        util.run_cmd(cmd)
            else:
                logger.warning(f"helm - no helm repos specified in {filename}")
        # helm deployments
        helm_list = util.run_cmd_json(["helm", "list", "--output", "json"])
        helm_deployments = list(map(lambda x: x["name"], helm_list))
        logger.debug(f"helm deployments installed: {helm_deployments}")
        if config["name"] in helm_deployments:
            logger.info(f"helm - already installed:{config['name']}")
        else:
            logger.info(f"helm - installing:{config['name']}")
            cmd = base_cmd + ["helm", helm_command, config["name"], config["install"]]
            util.run_cmd(cmd)

    except KeyError as e:
        raise RuntimeError(f"helm - {filename} missing key: {e}")
