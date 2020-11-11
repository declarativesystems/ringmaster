import re
import os
from . import constants
from loguru import logger
import subprocess
import requests
import snakecase


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


def run_cmd(cmd, data=None):
    if not data:
        data = {}
    env = merge_env(data)
    logger.trace(f"merged environment: {env}")
    logger.debug(f"running command: {cmd}")

    with subprocess.Popen(cmd,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          shell=isinstance(cmd, str),
                          env=env) as proc:
        while True:
            output = proc.stdout.readline()
            if proc.poll() is not None:
                break
            if output:
                logger.log("OUTPUT", output.decode("UTF-8").strip())
        rc = proc.poll()
        logger.debug(f"result: {rc}")
        if rc != 0:
            raise RuntimeError(f"Command failed with non-zero exit status:{rc} - {cmd}")


def flatten_nested_dict(data):
    flattened = {}
    for k, v in walk(data):
        flattened[k.lower()] = v

    return flattened


def substitute_placeholders_line(line, data):
    replacement_tokens = re.findall(constants.SUBSTITUTE_VARIABLE_REGEX, line)
    # set is used to de-dupe the list
    for replacement_token in list(set(replacement_tokens)):
        # chomp the ${} leaving the variable name
        replacement_token_name = replacement_token[2:-1]
        resolved_token = data.get(replacement_token_name)
        if resolved_token:
            line = line.replace(replacement_token, resolved_token)
        else:
            raise KeyError(f"requested field: {replacement_token_name} missing from databag. Available: {data.keys()}")

    return line


def substitute_placeholders_in_file(filename, comment_delim, data):
    """replace all variables placeholders in filename, return path to substituted file"""
    filename_no_extension, file_extension = os.path.splitext(filename)
    processed_file = filename_no_extension + ".processed" + file_extension
    if os.path.exists(filename):
        with open(processed_file, "w") as out_file:
            out_file.write(f"{comment_delim} This file was automatically generated from file: {filename}, do not edit!\n")
            with open(filename, "r") as in_file:
                for line in in_file:
                    out_file.write(substitute_placeholders_line(line, data))
    else:
        raise RuntimeError(f"No such file: {filename}")

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
