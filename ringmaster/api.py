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
from datetime import datetime
from urllib.parse import urlparse, urlunparse
import importlib
import requests
import os
import glob
import yaml
import json
import sys
import tempfile
from loguru import logger
from ringmaster import constants as constants
import ringmaster.k8s as k8s
import ringmaster.aws as aws
import ringmaster.snowflake as snowflake
from pathlib import Path
import ringmaster.version as version
import ringmaster.util as util
import ringmaster.cloudflare as cloudflare

debug = False

metadata = {
    "ringmaster_version": version.__version__,
    "generated_at": datetime.now().isoformat(),
    "description": "edit me",
    constants.METADATA_FILES_KEY: {},
}

# munged directory containing databag user supplied on the commandline
env_dir = None


def init_databag():
    """per-run program specific data"""

    # users write values as JSON to this file and they are added to the
    # databag incrementally
    _, intermediate_databag_file = tempfile.mkstemp(suffix="json", prefix="ringmaster")

    return {
        constants.KEY_INTERMEDIATE_DATABAG: intermediate_databag_file,
        "debug": "debug" if debug else "",
    }


def load_databag(databag_file):
    # load values from user
    data = {}
    if os.path.exists(databag_file):
        with open(databag_file) as f:
            data.update(yaml.safe_load(f))
    else:
        logger.warning(f"missing databag file: {databag_file}")

    logger.debug(f"loaded databag contents: {data}")
    return data


def load_intermediate_databag(data):
    intermediate_databag_file = data[constants.KEY_INTERMEDIATE_DATABAG]
    if os.path.getsize(intermediate_databag_file):
        # grab stashed databag
        logger.debug(f"loading databag left by last stage from {intermediate_databag_file}")
        with open(intermediate_databag_file, "r") as json_file:
            extra_data = json.load(json_file)

        logger.debug(f"loaded {len(extra_data)} items: {extra_data}")
        data.update(extra_data)

        # empty the bag for next iteration
        open(intermediate_databag_file, 'w').close()


def do_bash_script(working_dir, filename, verb, data):
    # bash scripts
    logger.info(f"bash script: {filename}")
    logger.info(f"write JSON to file at ${constants.KEY_INTERMEDIATE_DATABAG} to add to databag")
    util.run_cmd(f"bash {filename} {verb}", data)

    load_intermediate_databag(data)


# see
# https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
def do_ringmaster_python(working_dir, filename, verb, data):
    logger.info(f"ringmaster python: {filename}")
    # /foo/bar/baz.py -> baz
    module_name, _ = os.path.splitext(os.path.basename(filename))
    spec = importlib.util.spec_from_file_location(module_name, filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    # load data and run plugin
    # logger.enable("storage_security_groups.ringmaster")
    # logger.enable("storage_security_groups")
    # logger.enable("__main__")
    # logger.enable(module_name)
    # module.loggey = logger
    module.databag = data
    module.main(verb)


handlers = {
    constants.PATTERN_BASH: do_bash_script,
    constants.PATTERN_LOCAL_CLOUDFORMATION_FILE: aws.do_local_cloudformation,
    constants.PATTERN_REMOTE_CLOUDFORMATION_FILE: aws.do_remote_cloudformation,
    constants.PATTERN_KUBECTL_FILE: k8s.do_kubectl,
    constants.PATTERN_KUSTOMIZATION_FILE: k8s.do_kustomizer,
    constants.PATTERN_RINGMASTER_PYTHON_FILE: do_ringmaster_python,
    constants.PATTERN_SNOWFLAKE_SQL: snowflake.do_snowflake_sql,
    constants.PATTERN_SNOWFLAKE_QUERY: snowflake.do_snowflake_query,
    constants.PATTERN_HELM_DEPLOY: k8s.do_helm,
    constants.PATTERN_AWS_IAM_POLICY: aws.do_iam_policy,
    constants.PATTERN_AWS_IAM_ROLE: aws.do_iam_role,
    constants.PATTERN_SECRETS_MANAGER: aws.do_secrets_manager,
    constants.PATTERN_EKSCTL_CONFIG: aws.do_eksctl,
    constants.PATTERN_SECRET_KUBECTL: k8s.do_secret_kubectl,
    constants.PATTERN_CLOUDFLARE: cloudflare.do_cloudflare,
}


def get_handler_for_file(filename):
    handler = None
    for pattern in  handlers.keys():
        if filename.endswith(pattern):
            handler = handlers[pattern]
            break
    return handler



def do_file(working_dir, filename, verb, data):
    handler = get_handler_for_file(filename)
    if handler and verb == constants.METADATA_VERB:
        metadata[constants.METADATA_FILES_KEY][os.path.basename(filename)] = {
            constants.METADATA_HASH_KEY: util.hash_file(filename)
        }
    elif handler:
        handler(working_dir, filename, verb, data)
    else:
        logger.debug(f"no handler for {filename} - skipped")


def do_stage(working_dir, data, stage, verb):
    """process the children of an 'inner' dir in order, eg:
    stacks/
        0010 <--- this level
            somefile.yaml
    """
    for root, dirs, files in os.walk(stage, topdown=True, followlinks=True):
        # modify dirs in-place to exclude dirs to skip and all their children
        # https://stackoverflow.com/a/19859907/3441106
        dirs[:] = list(filter(lambda x: not x == constants.SKIP_DIR, dirs))

        # and then sort the files...
        files.sort()
        for file in files:
            filename = os.path.join(root, file)
            do_file(working_dir, filename, verb, data)

        if verb != constants.METADATA_VERB:
            save_output_databag(data)


def system_info():
    aws_version = util.run_cmd(["aws", "--version"]).strip()
    eksctl_version = util.run_cmd(["eksctl", "version"]).strip()
    kubectl_version = util.run_cmd(["kubectl", "version", "--short", "--client"]).strip()
    helm_version = util.run_cmd(["helm", "version", "--short"])

    message = util.process_res_template(
        "system_info.txt",
        aws_version=aws_version,
        boto3_version=aws.boto3_version(),
        cloudflare_version=cloudflare.cloudflare_version(),
        eksctl_version=eksctl_version,
        helm_version=helm_version,
        kubectl_version=kubectl_version,
        snowflake_connector_version=snowflake.snowflake_connector_version()
    )

    logger.info(message)


def setup_connections():

    connections = get_env_connections()
    aws.setup_connection(connections.get("aws"))
    snowflake.setup_connection(connections.get("snowflake"))
    k8s.setup_connection(connections.get("k8s"))

    # no connection info for cloudflare - you can only manage a DNS zone once
    # so this will either work or it wont...

def run(project_dir, filename, merge, env_name, verb):
    if os.path.exists(filename):
        data = get_env_databag(os.getcwd(),merge, env_name)
        setup_connections()

        do_file(project_dir, filename, verb, data)
        save_output_databag(data)
    else:
        logger.error(f"file not found: {filename}")


def delete_output_databag():
    output_databag_file = get_output_databag_filename()
    if os.path.exists(output_databag_file):
        logger.debug(f"deleting databag: {output_databag_file}")
        os.unlink(output_databag_file)


def save_output_databag(data):
    output_databag_file = get_output_databag_filename()
    logger.info(f"saving output databag:{output_databag_file}")
    util.save_yaml_file(
        output_databag_file,
        data,
        "# generated by ringmaster, do not edit!\n"
    )


def run_dir(working_dir, subdir, merge, env_name, start, verb):
    """process an 'outer' dir and all its children in order, eg:
    stacks/ <--- this level
        0010
            somefile.yaml
    """
    if os.path.exists(subdir):
        logger.debug(f"found: {subdir}")
        started = False

        data = get_env_databag(os.getcwd(), merge, env_name)
        setup_connections()

        # for some reason the default order is reversed when using ranges so we
        # must always sort. If we are bringing down a stack, reverse the order
        # to process steps last->first - dont rely on strange behaviour
        stages = sorted(glob.glob(f"./{subdir}/[0-9][0-9][0-9][0-9]*"), reverse=(verb == constants.DOWN_VERB))
        first_dir = os.path.basename(stages[0])
        last_dir = os.path.basename(stages[-1])
        if not start:
            start = first_dir if constants.UP_VERB else last_dir
            logger.debug(f"setting start dir:{start}")

        for stage in stages:
            logger.debug(stage)
            if not started:
                number = os.path.basename(stage)
                if number == start:
                    started = True

            if started:
                logger.debug(f"stage: {stage}")
                do_stage(working_dir, data, stage, verb)

        if not started:
            logger.error(f"start dir - not found: {start}")

        # cleanup
        logger.debug("delete intermediate databag")
        os.unlink(data[constants.KEY_INTERMEDIATE_DATABAG])

        if verb == constants.DOWN_VERB:
            delete_output_databag()

    else:
        logger.error(f"missing directory: {subdir}")


def check_ok_to_update(local_metadata_file, remote_url):
    safe = True
    working_dir = os.path.dirname(local_metadata_file)
    if os.path.exists(local_metadata_file):
        logger.debug(f"loading metadata:{local_metadata_file}")
        with open(local_metadata_file) as f:
            local_metadata = yaml.safe_load(f)
            logger.debug(f"metadata loaded:{local_metadata}")
        local_url = local_metadata.get(constants.SOURCE_KEY)
        if local_url == remote_url:
            for filename, file_metadata in local_metadata.get(constants.METADATA_FILES_KEY, {}).items():
                local_filename = os.path.join(working_dir, filename)
                if os.path.exists(local_filename) and \
                        util.hash_file(local_filename) != file_metadata[constants.METADATA_HASH_KEY]:
                    logger.error(f"file:{local_filename} MODIFIED - aborting. Delete and retry to overwrite")
                    safe = False
        else:
            logger.error(f"file:{local_metadata_file} source:{local_url} does not match requested:{remote_url} - aborting. Try saving to another directory")
            safe = False
    return safe


def download_metadata_yaml(url):
    # append METADATA_FILE to the end of path if missing...
    metadata_url = util.change_url_filename(url, constants.METADATA_FILE)
    return yaml.safe_load(requests.get(metadata_url).text)


def download_files_from_metadata(directory, new_metadata, base_url):
    """ download each file listed in new_metadata['files'] to `directory` """
    for filename, file_metadata in new_metadata.get(constants.METADATA_FILES_KEY, {}).items():
        local_file = os.path.join(directory, filename)
        remote_url = util.change_url_filename(base_url, filename)

        logger.info(f"downloading {remote_url} ==> {local_file}")
        downloaded_file = requests.get(remote_url)
        with open(local_file, "wb") as f:
            f.write(downloaded_file.content)

        if not util.hash_file(local_file) == new_metadata[constants.METADATA_FILES_KEY][filename][constants.METADATA_HASH_KEY]:
            raise RuntimeError(f"local hash != remote hash file:{filename}")


def get(directory, url):
    """download <url> to <dir> - somewhat inspired by go get"""
    if not os.path.exists(directory):
        Path(directory).mkdir(parents=True, exist_ok=True)

    local_metadata_file = os.path.join(directory, constants.METADATA_FILE)
    if check_ok_to_update(local_metadata_file, url):
        new_metadata = download_metadata_yaml(url)
        download_files_from_metadata(directory, new_metadata, url)

        # save the metadata file and add the source we downloaded from
        new_metadata[constants.SOURCE_KEY] = url
        util.save_yaml_file(local_metadata_file, new_metadata)


def include_extra_file(directory, extra_file):
    extra_file_path = os.path.join(directory, extra_file)
    if os.path.exists(extra_file_path):
        metadata[constants.METADATA_FILES_KEY][extra_file] = {
            constants.METADATA_HASH_KEY: util.hash_file(extra_file_path)
        }
    else:
        raise RuntimeError(f"Requested --include {extra_file_path} not found")


def write_metadata(directory, includes):
    extra_files = includes.split(",") if includes else []
    metadata_file = os.path.join(directory, constants.METADATA_FILE)
    name = os.path.basename(os.path.abspath(directory))
    metadata[constants.METADATA_NAME_KEY] = name
    logger.info(f"Collecting metadata for {directory} to {metadata_file} (--includes:{extra_files})")
    if os.path.isdir(directory):
        do_stage({}, directory, constants.METADATA_VERB)

        # now add any extra includes
        for extra_file in extra_files:
            include_extra_file(directory, extra_file)
    else:
        raise RuntimeError(f"No such directory: {directory}")

    util.save_yaml_file(metadata_file, metadata)


def get_env_dir(working_dir, env_name):
    env_dir_section = env_name if env_name else ""
    dirs = list(
        filter(
            lambda x: x is not None,
            [working_dir, constants.ENV_DIR, env_dir_section]
        )
    )
    return os.path.join(*dirs)


def get_env_connections():
    """read `connections.yaml` for this environment"""
    if not env_dir:
        raise RuntimeError("env_dir not set yet, load databags first")

    connections_yaml_filename = os.path.join(env_dir, constants.CONNECTIONS_YAML)
    return util.read_yaml_file(connections_yaml_filename)


def get_env_databag(working_dir, merge, env_name):
    """read the databag for this `env_name` with optional merging of any
    parent databags"""
    global env_dir

    # deepest directory to load databag from, with optional merging
    # examples: .env, .env/prod, .env/prod/australia
    env_dir = get_env_dir(working_dir, env_name)

    sequential_load_dirs = []
    look_at_dir = env_dir
    max_parents = 4
    depth = 0
    if merge:
        # add parent directory until we get back to .env
        while look_at_dir != working_dir:
            if depth > max_parents:
                raise RuntimeError(f".env dir nested too deep! (limit: {max_parents+1}")
            sequential_load_dirs.append(look_at_dir)
            look_at_dir = os.path.dirname(look_at_dir)
            depth += 1
        sequential_load_dirs.reverse()
    else:
        sequential_load_dirs.append(env_dir)

    logger.debug(f"sequential load dirs: {sequential_load_dirs}")

    # shallow
    data = constants.DEFAULT_DATABAG.copy()
    for look_at_dir in sequential_load_dirs:
        databag_file = os.path.join(look_at_dir, constants.DATABAG_FILE)
        output_databag_file = os.path.join(look_at_dir, constants.OUTPUT_DATABAG_FILE)
        target_databag_file = output_databag_file \
            if os.path.exists(output_databag_file) else databag_file
        data.update(load_databag(target_databag_file))

    data.update(init_databag())
    # `env` will clash with scoped environment variables
    data[constants.DATABAG_ENV_KEY] = env_name
    return data


def get_output_databag_filename():
    if not env_dir:
        raise RuntimeError("databag_load_dir not set, databag not loaded yet")
    return os.path.join(env_dir, constants.OUTPUT_DATABAG_FILE)
