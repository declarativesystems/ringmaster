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
    if os.path.exists(filename):
        with open(filename) as f:
            config = yaml.safe_load(f)
        try:
            git_repo = config['rkubelog']['git_repo']
        except KeyError:
            raise RuntimeError(f"missing yaml value for `rkubelog:git_repo` in  {filename}")

        try:
            # grab the secret from the hash and make sure all required keys
            # present
            secret = config['secret']
            _ = config['secret']["PAPERTRAIL_PROTOCOL"]
            _ = config['secret']["PAPERTRAIL_HOST"]
            _ = config['secret']["PAPERTRAIL_PORT"]
            _ = config['secret']["LOGGLY_TOKEN"]
        except KeyError as e:
            raise RuntimeError(f"solarwinds papertrail - missing yaml key:{e} file:{filename}")

        # defined in rkubelog source code - see link at top of this file
        if verb == constants.UP_VERB:
            k8s.register_k8s_secret("kube-system", "logging-secret", secret)
            copy_files_from_git(git_repo, download_dir)
        elif verb == constants.DOWN_VERB:
            k8s.delete_k8s_secret("kube-system", "logging-secret")
        else:
            raise RuntimeError(f"solarwinds papertrail - invalid verb:{verb}")

        kustomizer_file = os.path.join(
            download_dir,
            constants.PATTERN_KUSTOMIZATION_FILE
        )
        k8s.do_kustomizer(kustomizer_file, verb)

    else:
        raise RuntimeError(f"solarwinds papertrail - missing config file:{filename}")

