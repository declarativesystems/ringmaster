import snowflake.connector
import os
from loguru import logger
import yaml
import ringmaster.util as util
import ringmaster.constants as constants

SNOWFLAKE_CONFIG_FILE = "~/.ringmaster/snowflake.yaml"


def get_cursor():
    snowflake_config_file = os.path.expanduser(SNOWFLAKE_CONFIG_FILE)
    if os.path.exists(snowflake_config_file):
        with open(snowflake_config_file) as f:
            config = yaml.safe_load(f)
        ctx = snowflake.connector.connect(**config)
        cs = ctx.cursor(snowflake.connector.DictCursor)
    else:
        raise RuntimeError(f"snowflake settings not found at: {snowflake_config_file}")

    test_connection(cs)
    return cs


def test_connection(cs):
    cs.execute("SELECT current_version()")
    one_row = cs.fetchone()


def process_file_and_connect(filename, data):
    # process substitutions
    processed_file = util.substitute_placeholders_in_file(
        filename, constants.COMMENT_SQL, data
    )
    logger.debug(f"snowflake processed file: {processed_file}")

    # connect to snowflake, bail if it fails
    cs = get_cursor()
    return cs, processed_file


def do_snowflake_sql(filename, verb, data):
    """Run an SQL script with substition variables"""
    logger.info(f"snowflake sql: {filename}")
    cs, processed_file = process_file_and_connect(filename, data)

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


def do_snowflake_query(filename, verb, data):
    """Query snowflake for a single row of values, add each column to the databag"""
    logger.info(f"snowflake query: {filename}")
    cs, processed_file = process_file_and_connect(filename, data)
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