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
import yaml
import tempfile
import os
import shutil
from loguru import logger
from .util import run_cmd
import ringmaster.k8s as k8s
from pathlib import Path
from ringmaster import constants as constants
# support for solarwinds papertrail based on
# https://documentation.solarwinds.com/en/Success_Center/papertrail/Content/kb/configuration/rkubelog.htm?cshid=ptm-rkubelog


def copy_files_from_git(git_repo, dest_dir):
    if os.path.exists(dest_dir):
        logger.info(f"papertrail kustomization files already exist at {dest_dir}")
    else:
        logger.debug(f"downloading from git: {git_repo} to local:{dest_dir}")
        # checkout to tempdir
        tempdir = tempfile.mkdtemp(prefix="ringmaster")
        # todo - git branch/tag
        run_cmd(f"git clone {git_repo} {tempdir}")

        # copy-out kustomizer files to local dir for repeatable builds
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        k8s.copy_kustomization_files(tempdir, dest_dir)
        logger.debug(f"deleteing tempdir: {tempdir}")
        shutil.rmtree(tempdir)


def do_papertrail(filename, verb, data):
    # fixme - this should just be a generic way of downloading krazy
    # komplicated kustomizer files from git...

    logger.info(f"solarwinds papertrail: {filename}")
    # download to relative path within this step:
    # stack/up/.../
    # ├── download
    # │   └── rkubelog
    # └── solarwinds_papertrail.yaml
    download_dir = os.path.join(
        os.path.dirname(filename),
        constants.SKIP_DIR,
        "rkubelog"
    )

    with open(filename) as f:
        config = yaml.safe_load(f)
    try:
        git_repo = config['rkubelog']['git_repo']
    except KeyError:
        raise RuntimeError(f"missing yaml value for `rkubelog:git_repo` in  {filename}")

    # defined in rkubelog source code - see link at top of this file
    if verb == constants.UP_VERB:
        copy_files_from_git(git_repo, download_dir)
    elif verb == constants.DOWN_VERB:
        pass
    else:
        raise RuntimeError(f"solarwinds papertrail - invalid verb:{verb}")

    kustomizer_file = os.path.join(
        download_dir,
        constants.PATTERN_KUSTOMIZATION_FILE
    )
    k8s.do_kustomizer(kustomizer_file, verb)


