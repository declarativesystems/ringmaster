"""ringmaster

Usage:
  ringmaster [--debug] <dir> (up|down) [--start=<dir>]
  ringmaster [--debug] --init --aws
  ringmaster [--debug] --run (up|down) <filename>
  ringmaster --version

Options:
  -h --help     Show this screen.
  --version     Show version.
  --debug       Extra debugging messages
  --start=<dir_num>  up: start here and count up, down: start here and count down
"""

from loguru import logger
import pkg_resources
import sys
from docopt import docopt
import ringmaster.aws as aws
import ringmaster.api as api
import ringmaster.constants as constants

debug = False

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
    api.debug = arguments['--debug']
    logger.debug(f"parsed arguments: ${arguments}")
    exit_status = 1
    try:

        if arguments['--init']:
            exit_status = aws.aws_init()
        else:
            if arguments["down"]:
                verb = constants.DOWN_VERB
            elif arguments["up"]:
                verb = constants.UP_VERB
            else:
                raise RuntimeError("one of (up|down) is required")

            if arguments["<dir>"]:
                exit_status = api.run_dir(arguments["<dir>"], arguments['--start'], verb)
            elif arguments["--run"]:
                exit_status = api.run(arguments['<filename>'], verb)
            else:
                raise RuntimeError("one of <dir> or --run expected")


    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logger.error(str(exc_value))
        if arguments['--debug']:
            logger.exception(e)

    sys.exit(exit_status)
