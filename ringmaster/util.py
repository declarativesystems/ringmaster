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
from . import constants
from loguru import logger
import subprocess
import requests
import snakecase
import json
from contextlib import ExitStack
from halo import Halo
import hashlib
import base64
from jinja2 import Environment, Template, StrictUndefined, Undefined
from jinja2.exceptions import UndefinedError
import yaml
import pathlib


def walk(data, parent_name=None):
    seq_iter = data if isinstance(data, dict) else range(len(data))
    for i in seq_iter:
        if parent_name:
            me = f"{parent_name}_{i}"
        else:
            me = i

        if isinstance(data[i], dict):
            for k, v in walk(data[i], parent_name=me):
                yield k, v
        elif isinstance(data[i], list) or isinstance(data[i], tuple):
            for k, v in walk(data[i], parent_name=me):
                yield k, v
        else:
            yield me, data[i]


def convert_dict_values_to_string(data):
    # all values passed to os.environ must be strings, avoid unwanted yaml help
    for key in data:
        data[key] = str(data[key])


def merge_env(data):
    env = os.environ.copy()
    env.update(data)

    convert_dict_values_to_string(env)
    return env


def run_cmd_json(cmd, data=None):
    """Run a command and parse JSON from its output"""
    string = run_cmd(cmd, data=data)
    logger.debug(f"string to parse: {string}")
    return json.loads(string)


def run_cmd(cmd, data=None):
    if not data:
        data = {}
    output = ""
    env = merge_env(data)
    logger.trace(f"merged environment: {env}")
    logger.debug(f"running command: {cmd}")
    debug = data.get("debug", False)
    with ExitStack() as stack:
        if not debug:
            stack.enter_context(Halo(text=f"Running {cmd}", spinner='dots'))

        with subprocess.Popen(cmd,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              shell=isinstance(cmd, str),
                              env=env) as proc:
            while True:
                line = proc.stdout.readline()
                while line:
                    line_decoded = line.decode("UTF-8")
                    if debug:
                        logger.log("OUTPUT", line_decoded.strip())
                    output += line_decoded

                    line = proc.stdout.readline()
                if proc.poll() is not None:
                    break
        rc = proc.poll()
        logger.debug(f"result: {rc}")
        if rc != 0:
            logger.error(output)
            raise RuntimeError(f"Command failed with non-zero exit status:{rc} - {cmd}")
    return output


def flatten_nested_dict(data):
    flattened = {}
    for k, v in walk(data):
        flattened[k.lower()] = v

    return flattened


def base64encode(string):
    string_bytes = string.encode('ascii')
    base64_bytes = base64.b64encode(string_bytes)
    return base64_bytes.decode('ascii')


def get_res_filename(filename):
    return os.path.join(
        os.path.dirname(
            os.path.realpath(__file__)
        ),
        "res",
        filename
    )


def get_res_file_content(filename):
    with open(get_res_filename(filename), "r") as f:
        return f.read()


def process_res_template(filename, **data):
    """process a template from the /res directory and return it as a string"""
    template = Template(get_res_file_content(filename))
    return template.render(**data)


def substitute_placeholders_from_memory_to_memory(raw, verb, data):
    """replace all variables placeholders list of lines and return the result"""

    # allow missing variables in templates if we are going down
    undefined = StrictUndefined if verb == constants.UP_VERB else Undefined
    jinja_env = Environment(undefined=undefined, keep_trailing_newline=True)
    # compatible name with Ansible filters
    jinja_env.filters['b64encode'] = base64encode
    template = jinja_env.from_string(raw)
    # add `env` key with contents of environment
    data_with_env = {**data, "env": os.environ.copy()}

    try:
        buffer = template.render(data_with_env)
    except UndefinedError as e:
        if verb == constants.DOWN_VERB:
            logger.warning(f"returning original content due to: {e}")
            buffer = raw
        else:
            raise e
    return buffer


def substitute_placeholders_from_file_to_memory(filename, verb, data):
    """replace all variables placeholders in filename and return the result"""
    if os.path.exists(filename):
        with open(filename, "r") as in_file:
            buffer = substitute_placeholders_from_memory_to_memory(
                in_file.read(),
                verb,
                data
            )
    else:
        raise RuntimeError(f"No such file: {filename}")

    return buffer


def get_processed_filename(working_dir, input_filename, env_name):
    """Return the filename where we should save the processed version of
    `input_filename`"""
    if input_filename.startswith("/"):
        raise RuntimeError(f"input_filename must be a relative path, received: {input_filename}")

    dirs = filter(
        lambda x: x is not None,
        [working_dir, constants.PROCESSED_DIR, env_name, input_filename]
    )
    processed_filename = os.path.join(*dirs)

    if os.path.abspath(input_filename) == os.path.abspath(processed_filename):
        raise RuntimeError(f"filename and processed_filename refer to the same file: {input_filename}")

    return os.path.normpath(processed_filename)


def substitute_placeholders_from_file_to_file(working_dir, filename, comment_delim, verb, data):
    """replace all variables placeholders in filename, return path to substituted file"""
    processed_file = get_processed_filename(working_dir, filename, data.get(constants.DATABAG_ENV_KEY))
    logger.debug(f"substitute placeholders: {filename} => {processed_file}")
    abs_filename = os.path.normpath(os.path.join(working_dir, filename))
    if os.path.exists(abs_filename):
        # create parent directory for processed file if needed
        pathlib.Path(os.path.dirname(processed_file)).mkdir(parents=True, exist_ok=True)
        with open(processed_file, "w") as out_file:
            out_file.write(f"{comment_delim} This file was automatically generated from file: {filename}, do not edit!\n")
            with open(abs_filename, "r") as in_file:
                out_file.write(
                    substitute_placeholders_from_memory_to_memory(
                        in_file.read(),
                        verb,
                        data,
                    )
                )
    else:
        raise RuntimeError(f"No such file: {abs_filename}")
    return processed_file


def download(url, filename):
    downloaded = requests.get(url, allow_redirects=True)
    open(filename, 'wb').write(downloaded.content)


# convert `number` to `_number` to match databag
def string_to_snakecase(string):
    # there are two conversion patterns in use which convert as follows:
    #   1. lowercase-hypen-separated -> lowercase_hyphen_separated
    #   2. mixed-CasePascalCaseAndHyphenSeparated -> mixed_case_pascal_case_and_hyphen_separated
    # AWS public cloudformation scripts use option 2 ;-)
    if string.lower() == string:
        # lower case
        string = string.replace("-", "_")
    else:
        # mixed case
        string = string.replace("-", "")

    key = snakecase.convert(string)

    logger.debug(f"converted input:{string} key:{key}")
    return key


def hash_file(filename):
    return hashlib.sha1(pathlib.Path(filename).read_bytes()).hexdigest()


def change_url_filename(url, filename):
    """change the filename in the last part of url if needed, eg:
        change_url_filename("https://blah", "something.txt") # https://blah/something.txt
    """
    return f"{url}/{filename}"


def read_yaml_file(filename):
    """read a yaml file and return it"""
    with open(filename) as f:
        yaml_data = yaml.safe_load(f)

    if yaml_data is None:
        raise RuntimeError(f"No YAML data in file: {filename}")

    return yaml_data


def save_yaml_file(filename, data, comment=None):
    """save yaml data to file, creating any directories as needed"""
    dirname = os.path.dirname(filename)
    pathlib.Path(dirname).mkdir(parents=True, exist_ok=True)
    with open(filename, "w") as f:
        if comment:
            f.write(comment)
        yaml.dump(data, f)


def get_connection_profile(connection, caller_name):
    """get the kubectl context to run with context set or bomb out"""
    if not connection.get(constants.PROFILE):
        raise RuntimeError(f"No profile set for {caller_name}")

    return connection[constants.PROFILE]