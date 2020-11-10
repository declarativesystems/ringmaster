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
        cs = ctx.cursor()
    else:
        raise RuntimeError(f"snowflake settings not found at: {snowflake_config_file}")

    return cs

def test_connection(cs):
    cs.execute("SELECT current_version()")
    one_row = cs.fetchone()


def do_snowflake_sql(filename, verb, data):
    logger.info(f"snowflake sql: {filename}")

    # process substitutions
    processed_file = util.substitute_placeholders_in_file(
        filename, constants.COMMENT_SQL, data
    )
    logger.debug(f"snowflake processed file: {processed_file}")

    # connect to snowflake, bail if it fails
    cs = get_cursor()
    test_connection(cs)

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
                    stmt=""
