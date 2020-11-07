import yaml
import tempfile
import os
from loguru import logger
from .util import run_cmd
from .k8s import copy_kustomization_files
from .k8s import register_k8s_secret
from .k8s import run_kustomizer
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
    copy_kustomization_files(tempdir, target_dir)


def install_solarwinds_papertrail(config_file, data):
    if os.path.exists(config_file):
        logger.info(f"solarwinds papertrail: {config_file}")
        with open(config_file) as f:
            config = yaml.safe_load(f)
        try:
            git_repo = config['rkubelog']['git_repo']
        except KeyError:
            raise RuntimeError(f"missing yaml value for `rkubelog:git_repo` in  {config_file}")

        try:
            # grab the secret from the hash and make sure all required keys
            # present
            secret = config['secret']
            _ = config['secret']["PAPERTRAIL_PROTOCOL"]
            _ = config['secret']["PAPERTRAIL_HOST"]
            _ = config['secret']["PAPERTRAIL_PORT"]
            _ = config['secret']["LOGGLY_TOKEN"]
        except KeyError as e:
            raise RuntimeError(f"solarwinds papertrail - missing yaml key:{e} file:{config_file}")


        # defined in rkubelog source code - see link at top of this file
        register_k8s_secret("kube-system", "logging-secret", secret)
        copy_files_from_git(git_repo)
        run_kustomizer(constants.RES_KUSTOMIZER_RKUBELOG_DIR, "apply")

    else:
        raise RuntimeError(f"solarwinds papertrail - missing config file:{config_file}")

