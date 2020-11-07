"""ringmaster

Usage:
  ringmaster [--debug] init --aws
  ringmaster [--debug] up [--goto=<dir>]
  ringmaster [--debug] down [--goto=<dir>]
  ringmaster [--debug] user-up [--goto=<dir>]
  ringmaster [--debug] user-down [--goto=<dir>]
  ringmaster --version

Options:
  -h --help     Show this screen.
  --version     Show version.
  --debug       Extra debugging messages
  --goto=<dir>  Start from <dir> [default: 0010]
"""

from loguru import logger
import traceback
import pkg_resources
import sys
from docopt import docopt

from .aws import aws_init
from .api import up
from .api import down
from .api import user_up
from .api import user_down



# color logs
# https://stackoverflow.com/a/56944256/3441106
def setup_logging(level, logger_name=None):
    logger_name = logger_name or __name__.split(".")[0]
    log_formats = {
        "DEBUG": "{time} {level} {message}",
        "INFO": "{message}",
    }


    # custom level for program output so it can be nicely colourised
    logger.remove()
    logger.add(sys.stdout, format=log_formats[level], filter=logger_name, level=level)
    prog_level = logger.level("OUTPUT", no=25, color="<white><dim>", icon="🤡")

    logger.debug("====[debug mode enabled]====")


def main():
    arguments = docopt(__doc__, version=pkg_resources.require("ringmaster")[0].version)
    setup_logging("DEBUG" if arguments['--debug'] else "INFO")
    logger.debug(f"parsed arguments: ${arguments}")
    goto = arguments['--goto']
    exit_status = 1
    try:
        if arguments['init']:
            exit_status = aws_init()
        elif arguments['up']:
            exit_status = up(goto)
        elif arguments['down']:
            exit_status = down(goto)
        elif arguments['user-up']:
            exit_status = user_up(goto)
        elif arguments['user-down']:
            exit_status = user_down(goto)

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logger.error(str(exc_value))
        if arguments['--debug']:
            logger.exception(e)

    sys.exit(exit_status)