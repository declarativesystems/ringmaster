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
import snowflake.connector
import os
from loguru import logger
import yaml
import ringmaster.util as util
import ringmaster.constants as constants

SNOWFLAKE_CONFIG_FILE = "~/.ringmaster/snowflake.yaml"


def get_cursor(data):
    snowflake_config_file = os.path.expanduser(SNOWFLAKE_CONFIG_FILE)
    if os.path.exists(snowflake_config_file):
        with open(snowflake_config_file) as f:
            config = yaml.safe_load(f)
        ctx = snowflake.connector.connect(**config["credentials"])
        cs = ctx.cursor(snowflake.connector.DictCursor)

        # grab some convenince variables from snowflake settings
        data["snowflake_account"] = config["credentials"]["account"]
        data["snowflake_region"] = config["region"]
    else:
        raise RuntimeError(f"snowflake settings not found at: {snowflake_config_file}")

    test_connection(cs)
    return cs


def test_connection(cs):
    cs.execute("SELECT current_version()")
    one_row = cs.fetchone()


def process_file_and_connect(filename, verb, data):
    # process substitutions
    processed_file = util.substitute_placeholders_from_file_to_file(
        filename, constants.COMMENT_SQL, verb, data
    )
    logger.debug(f"snowflake processed file: {processed_file}")

    # connect to snowflake, bail if it fails
    cs = get_cursor(data)
    return cs, processed_file


def do_snowflake_sql(filename, verb, data):
    """Run an SQL script with substition variables"""
    script_name = os.path.basename(filename)
    if (verb == constants.UP_VERB and script_name != constants.SNOWFLAKE_CLEANUP_FILENAME) or \
            (verb == constants.DOWN_VERB and script_name == constants.SNOWFLAKE_CLEANUP_FILENAME):

        logger.info(f"snowflake sql: {filename}")
        cs, processed_file = process_file_and_connect(filename, verb, data)

        # build up stmt line-by-line, when we find `;` execute stmt and
        # empty the variable for the next iteration
        stmt = ""
        with open(processed_file, "r") as file:
            for line in file:
                if not line.startswith(constants.COMMENT_SQL):
                    stmt += line.rstrip()
                    if stmt.endswith(";"):
                        logger.debug(f"sql: {stmt}")
                        cs.execute(stmt)
                        stmt = ""
    else:
        logger.info(f"skippking snowflake: {filename}")


def do_snowflake_query(filename, verb, data):
    """Query snowflake for a single row of values, add each column to the databag"""
    if verb == constants.UP_VERB:
        logger.info(f"snowflake query: {filename}")
        cs, processed_file = process_file_and_connect(filename, verb, data)
        extra_data = {}

        # load the entire processed file and run EACH STATEMENT
        with open(processed_file, 'r') as file:
            sql = file.read()

        for stmt in sql.split(";"):
            logger.debug(f"snowflake sql query: {stmt}")
            cs.execute(stmt)

        result = cs.fetchone()
        logger.info(f"sql result: {result}")

        # result is a dict so just lowercase each key and add to databag
        for k, v in result.items():
            extra_data[k.lower()] = v

        logger.debug(f"query result - items: {len(extra_data)} values:{extra_data}")
        data.update(extra_data)