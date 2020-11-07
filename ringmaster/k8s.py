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
from .util import substitute_placeholders_in_file


def copy_kustomization_files(root_dir, target_dir):

    kustomization_file = os.path.join(root_dir, constants.KUSTOMIZATION_FILE)
    with open(kustomization_file) as f:
        kustomization_data = yaml.safe_load(f)

    # kustomization.yaml
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        kustomization_file, os.path.join(target_dir, constants.KUSTOMIZATION_FILE))
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
    run_cmd(["kubectl", "apply", "-f", secret_file])

    os.unlink(secret_file)


def run_kubectl(kubectl_file, verb, data):
    # substitute ${...} variables from databag, bomb out if any missing
    processed_file = substitute_placeholders_in_file(kubectl_file, data)
    logger.debug(f"kubectl processed file: {processed_file}")

    if verb == constants.UP_VERB or verb == constants.USER_UP_VERB:
        kubectl_cmd = "apply"
    elif verb == constants.DOWN_VERB or verb == constants.USER_DOWN_VERB:
        kubectl_cmd = "delete"
    else:
        raise ValueError(f"invalid verb: {verb}")

    run_cmd(["kubectl", kubectl_cmd,  "-f", processed_file], data)


def run_kustomizer(sources_dir, kubectl_cmd):
    run_cmd(["kubectl", kubectl_cmd, "-k", sources_dir])
