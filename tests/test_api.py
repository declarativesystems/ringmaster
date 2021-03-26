import os
import ringmaster.api as api
import pytest

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


def test_get_env_databag_child():
    """processes first child env"""
    data = api.get_env_databag(root_dir, True, "dev")
    assert data.get("new_value") == "new"
    assert data.get("parent_value") == "override"
    assert data.get("common_value") == "common"


def test_get_env_databag_output():
    """must read from output_databag.yaml and munge parents"""
    data = api.get_env_databag(root_dir, True, "prod")
    assert data.get("prod_value") == "prod"
    assert data.get("common_value") == "common"


def test_deep_nested_env_databag():
    """processes 2 level env hierarchy"""
    data = api.get_env_databag(root_dir, True, "dev/special")
    assert data.get("new_value") == "new"
    assert data.get("parent_value") == "override"
    assert data.get("common_value") == "common"
    assert data.get("special_value") == "special"

