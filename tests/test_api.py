import os
import ringmaster.api as api
import ringmaster.constants as constants
import pytest
from loguru import logger


# directory containing .env
root_dir = os.path.relpath(
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "tests")),
    os.getcwd()
)


def test_get_env_databag_raises():
    """Raise if there are too many directories to process"""
    with pytest.raises(RuntimeError):
        _ = api.get_env_databag(root_dir, True, "1/2/3/4/5")


def test_get_env_databag_parent():
    """processes top .env directory"""
    data = api.get_env_databag(root_dir, True, None)
    assert data.get("parent_value") == "top"
    assert api.get_output_databag_filename() == os.path.join(
        root_dir,
        constants.ENV_DIR,
        "output_databag.yaml"
    )
    assert data.get("env_name") is None


def test_get_env_databag_child():
    """processes first child env"""
    data = api.get_env_databag(root_dir, True, "dev")
    assert data.get("new_value") == "new"
    assert data.get("parent_value") == "override"
    assert data.get("common_value") == "common"
    assert api.get_output_databag_filename() == os.path.join(
        root_dir,
        constants.ENV_DIR,
        "dev/output_databag.yaml"
    )
    assert data.get("env_name") == "dev"


def test_get_env_databag_output():
    """must read from output_databag.yaml and munge parents"""
    data = api.get_env_databag(root_dir, True, "prod")
    assert data.get("prod_value") == "prod"
    assert data.get("common_value") == "common"
    assert api.get_output_databag_filename() == os.path.join(
        root_dir,
        constants.ENV_DIR,
        "prod/output_databag.yaml"
    )
    assert data.get("env_name") == "prod"


def test_deep_nested_env_databag():
    """processes 2 level env hierarchy"""
    data = api.get_env_databag(root_dir, True, "dev/special")
    assert data.get("new_value") == "new"
    assert data.get("parent_value") == "override"
    assert data.get("common_value") == "common"
    assert data.get("special_value") == "special"
    assert api.get_output_databag_filename() == os.path.join(
        root_dir,
        constants.ENV_DIR,
        "dev/special/output_databag.yaml"
    )
    assert data.get("env_name") == "dev/special"



def test_deep_nested_env_no_merge_databag():
    """merge flag is honored"""
    data = api.get_env_databag(root_dir, False, "dev/special")
    logger.debug(data)
    assert data.get("new_value") is None
    assert data.get("common_value") is None
    assert data.get("special_value") == "special"
    assert api.get_output_databag_filename() == os.path.join(
        root_dir,
        constants.ENV_DIR,
        "dev/special/output_databag.yaml"
    )


def test_databag_default_values():
    """default values must be loaded"""
    data = api.get_env_databag(root_dir, False, "dev/special")

    assert data.get("up_verb") == constants.UP_VERB


def test_databag_init_ok():
    """stale databag values must be updated with per-run settings"""
    data = api.get_env_databag(root_dir, False, "dev/special")

    assert data.get("intermediate_databag_file") is not None
    assert data.get("intermediate_databag_file") != "stale"
