import yaml
import tempfile
import os
import shutil
from loguru import logger
from .util import run_cmd
import ringmaster.k8s as k8s
from ringmaster import constants as constants
# support for solarwinds papertrail based on
# https://documentation.solarwinds.com/en/Success_Center/papertrail/Content/kb/configuration/rkubelog.htm?cshid=ptm-rkubelog


def copy_files_from_git(git_repo):
    logger.debug(f"downloading from git: {git_repo} to local:{constants.RES_KUSTOMIZER_RKUBELOG_DIR}")
    # checkout to tempdir
    tempdir = tempfile.mkdtemp(prefix="ringmaster")
    # todo - git branch/tag
    run_cmd(f"git clone {git_repo} {tempdir}")

    # copy-out kustomizer files to local dir for repeatable builds
    target_dir = os.path.join(constants.RES_KUSTOMIZER_RKUBELOG_DIR)
    k8s.copy_kustomization_files(tempdir, target_dir)
    logger.debug(f"deleteing tempdir: {tempdir}")
    shutil.rmtree(tempdir)


def setup(filename, verb, data):
    logger.info(f"solarwinds papertrail: {filename}")
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
        k8s.register_k8s_secret("kube-system", "logging-secret", secret)
        copy_files_from_git(git_repo)
        kustomizer_file = os.path.join(
            constants.RES_KUSTOMIZER_RKUBELOG_DIR,
            constants.PATTERN_KUSTOMIZATION_FILE
        )
        k8s.do_kustomizer(kustomizer_file, constants.UP_VERB)

    else:
        raise RuntimeError(f"solarwinds papertrail - missing config file:{filename}")

