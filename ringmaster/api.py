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
import ringmaster.solarwinds_papertrail as solarwinds_papertrail
from .util import run_cmd
import ringmaster.k8s as k8s
import ringmaster.aws as aws
import ringmaster.snowflake as snowflake

debug = False


def load_databag(databag_file):
    # users write values as JSON to this file and they are added to the
    # databag incrementally
    _, intermediate_databag_file = tempfile.mkstemp(suffix="json", prefix="ringmaster")

    # general program settings
    data = {
        "msg_up_to_date": constants.MSG_UP_TO_DATE,
    }

    # load values from user
    if os.path.exists(databag_file):
        with open(databag_file) as f:
            data.update(yaml.safe_load(f))
    else:
        logger.warning(f"missing databag file: {databag_file}")

    # per-run program specific data
    data.update({
        constants.KEY_INTERMEDIATE_DATABAG: intermediate_databag_file,
        "debug": "debug" if debug else "",
        "name": os.path.basename(os.getcwd()),
    })

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


def do_bash_script(filename, verb, data):
    # bash scripts
    logger.info(f"bash script: {filename}")
    run_cmd(f"bash {filename}", data)

    load_intermediate_databag(data)


# see
# https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
def do_ringmaster_python(filename, verb, data):
    logger.info(f"ringmaster python: {filename}")
    # /foo/bar/baz.py -> baz
    module_name, _ = os.path.splitext(os.path.basename(filename))
    spec = importlib.util.spec_from_file_location(module_name, filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    # load data and run plugin
    module.logger = logger
    module.databag = data
    module.main()


handlers = {
    constants.PATTERN_BASH: do_bash_script,
    constants.PATTERN_LOCAL_CLOUDFORMATION_FILE: aws.do_local_cloudformation,
    constants.PATTERN_REMOTE_CLOUDFORMATION_FILE: aws.do_remote_cloudformation,
    constants.PATTERN_KUBECTL_FILE: k8s.do_kubectl,
    constants.PATTERN_SOLARWINDS_PAPERTRAIL_FILE: solarwinds_papertrail.setup,
    constants.PATTERN_KUSTOMIZATION_FILE: k8s.do_kustomizer,
    constants.PATTERN_RINGMASTER_PYTHON_FILE: do_ringmaster_python,
    constants.PATTERN_SNOWFLAKE_SQL: snowflake.do_snowflake_sql,
    constants.PATTERN_SNOWFLAKE_QUERY: snowflake.do_snowflake_query,
    constants.PATTERN_HELM_DEPLOY: k8s.do_helm,
    constants.PATTERN_AWS_IAM_POLICY: aws.do_iam_policy,
    constants.PATTERN_AWS_IAM_ROLE: aws.do_iam_role,
    constants.PATTERN_SECRETS_MANAGER: aws.do_secrets_manager,
    constants.PATTERN_EKSCTL_CONFIG: aws.do_eksctl,
}


def get_handler_for_file(filename):
    handler = None
    for pattern in  handlers.keys():
        if filename.endswith(pattern):
            handler = handlers[pattern]
            break
    return handler


def do_file(filename, verb, data):
    handler = get_handler_for_file(filename)
    if handler:
        handler(filename, verb, data)
    else:
        logger.info(f"no handler for {filename} - skipped")


def do_stage(data, stage, verb):
    for root, dirs, files in os.walk(stage, topdown=True, followlinks=True):
        # modify dirs in-place to exclude dirs to skip and all their children
        # https://stackoverflow.com/a/19859907/3441106
        dirs[:] = list(filter(lambda x: not x == constants.SKIP_DIR, dirs))
        for file in files:
            filename = os.path.join(root, file)
            do_file(filename, verb, data)

        save_output_databag(data)


def stack(start, verb):
    return run_dir(os.path.join(constants.STACK_DIR, verb), start, verb)


def user(start, verb):
    return run_dir(os.path.join(constants.USER_DIR, verb), start, verb)


def run(filename, verb):
    if os.path.exists(filename):
        databag_file = constants.OUTPUT_DATABAG_FILE \
            if os.path.exists(constants.OUTPUT_DATABAG_FILE) else constants.DATABAG_FILE
        data = load_databag(databag_file)
        do_file(filename, verb, data)
    else:
        logger.error(f"file not found: {filename}")


def save_output_databag(data):
    logger.info(f"saving output databag:{constants.OUTPUT_DATABAG_FILE}")
    # save the updated databag for use in normal operation
    with open(constants.OUTPUT_DATABAG_FILE, "w") as f:
        f.write("# generated by ringmaster, do not edit!\n")
        yaml.dump(data, f)


def run_dir(working_dir, start, verb):
    if os.path.exists(working_dir):
        logger.debug(f"found: {working_dir}")
        started = False

        databag_file = constants.OUTPUT_DATABAG_FILE \
            if os.path.exists(constants.OUTPUT_DATABAG_FILE) \
            else constants.DATABAG_FILE
        data = load_databag(databag_file)

        # for some reason the default order is reveresed when using ranges
        for stage in sorted(glob.glob(f"./{working_dir}/[0-9][0-9][0-9][0-9]")):
            if not started:
                number = os.path.basename(stage)
                if number == start:
                    started = True

            if started:
                logger.debug(f"stage: {stage}")
                do_stage(data, stage, verb)

        if not started:
            logger.error(f"start dir - not found: {start}")

        # cleanup
        logger.debug("delete intermediate databag")
        os.unlink(data[constants.KEY_INTERMEDIATE_DATABAG])
        logger.debug("delete eksctl databag")
        os.unlink(data[constants.KEY_EKSCTL_DATABAG])

    else:
        logger.error(f"missing directory: {working_dir}")
