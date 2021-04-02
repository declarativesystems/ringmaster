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
"""ringmaster

Usage:
  ringmaster [--debug] <dir> (up|down) [--start=<dir>] [--env=<dir>] [--no-merge-env]
  ringmaster [--debug] get <dir> <url>
  ringmaster [--debug] metadata <dir> [--include=<files>]
  ringmaster [--debug] --run <filename> (up|down) [--env=<dir>] [--no-merge-env]
  ringmaster --version

Options:
  -h --help         Show this screen.
  --version         Show version.
  --debug           Extra debugging messages
  --env=<dir>       Read/write databags to this sub-directory under .env
                    otherwise just use .env. Databags will be merged with any
                    databags in the parent directory with child values taking
                    precedence unless --no-merge-env is used
  --no-merge-env    Do not merge databag values between env directories
  --start=<dir_num> up: start here count up, down: start here count down
  --include=<files> comma delimited list of extra files to add to metadata
"""

from loguru import logger
import sys
from docopt import docopt
import ringmaster.api as api
import ringmaster.version as version
import ringmaster.constants as constants
import os

debug = False

# color logs
# https://stackoverflow.com/a/56944256/3441106
def setup_logging(level, logger_name=None):
    logger_name = logger_name or __name__.split(".")[0]
    log_formats = {
        "DEBUG": "{time}<level> {level} [{module}] {message}</level>",
        "INFO": "<level>[{module}] {message}</level>",
    }


    # custom level for program output so it can be nicely colourised
    logger.remove()
    logger.debug(f"{logger_name} {level}")
    logger.add(sys.stdout, colorize=True, format=log_formats[level], level=level)
    prog_level = logger.level("OUTPUT", no=25, color="<white><dim>", icon="🤡")

    logger.debug("====[debug mode enabled]====")


def main():
    arguments = docopt(__doc__, version=version.__version__)
    setup_logging("DEBUG" if arguments['--debug'] else "INFO")
    api.debug = arguments['--debug']
    logger.debug(f"parsed arguments: ${arguments}")
    merge = not arguments.get("--no-merge-env")
    env_name = arguments["--env"]

    try:
        if arguments["down"]:
            verb = constants.DOWN_VERB
        elif arguments["up"]:
            verb = constants.UP_VERB
        elif arguments["get"]:
            verb = constants.GET_VERB
        elif arguments["metadata"]:
            verb = constants.METADATA_VERB
        else:
            raise RuntimeError("one of (up|down|get) is required")

        api.system_info()
        working_dir = os.getcwd()
        if arguments["get"]:
            api.get(arguments["<dir>"], arguments["<url>"])
        elif arguments["metadata"]:
            api.write_metadata(arguments["<dir>"], arguments.get("--include", []))
        elif arguments["<dir>"]:
            api.run_dir(working_dir, arguments["<dir>"], merge, env_name, arguments['--start'], verb)
        elif arguments["--run"]:
            api.run(working_dir, arguments['<filename>'], merge, env_name, verb)
        else:
            raise RuntimeError("one of <dir> or --run expected")

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logger.error(str(exc_value))
        if arguments['--debug']:
            logger.exception(e)

