import pytest
import ringmaster.util as util
import os
from jinja2.exceptions import UndefinedError
import ringmaster.constants as constants
import tempfile
import shutil
import pathlib


# directory containing .env
root_dir = os.path.relpath(
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "tests")),
    os.getcwd()
)

def test_string_to_snakecase():
    assert "lowercase_hyphen_separated" \
           == util.string_to_snakecase("lowercase-hyphen-separated")
    assert "mixed_case_pascal_case_and_hyphen_separated" \
           == util.string_to_snakecase("mixed-CasePascalCaseAndHyphenSeparated")


def test_same_line_count():
    """Check we have the same number of lines after processing template"""
    processed = util.substitute_placeholders_from_memory_to_memory(
        "one\ntwo\n",
        constants.UP_VERB,
        {}
    )
    assert processed == "one\ntwo\n"


def test_resolve_replacement_token():
    data = {
        "atoken": "avalue",
    }
    assert "avalue" == util.substitute_placeholders_from_memory_to_memory(
        "{{atoken}}",
        constants.UP_VERB,
        data
    )

    # raise on missing token
    with pytest.raises(UndefinedError):
        util.substitute_placeholders_from_memory_to_memory(
            "{{nohere}}",
            constants.UP_VERB,
            data
        )

    # no raise on missing token if going down
    util.substitute_placeholders_from_memory_to_memory(
        "{{nohere}}",
        constants.DOWN_VERB,
        data
    )

def test_filter_base64():
    """test the |b64encode filter"""
    data = {
        "atoken": "avalue",
    }
    assert util.substitute_placeholders_from_memory_to_memory(
        "{{atoken|b64encode}}",
        constants.UP_VERB,
        data
    ) == util.base64encode(data["atoken"])


def test_resolve_env():
    value = "avalue"

    # environment variables should be automatically resolveable via
    # `{{env.NAME}}`
    os.environ["x"] = value

    assert value == util.substitute_placeholders_from_memory_to_memory(
        "{{env.x}}",
        constants.UP_VERB,
        {},
    )

    with pytest.raises(UndefinedError):
        assert value == util.substitute_placeholders_from_memory_to_memory(
            "{{env.nothere}}",
            constants.UP_VERB,
            {},
        )


def test_change_url_filename():
    assert "https://github.com/declarativesystems/ringmaster/tree/master/examples/aws/eks-cluster/metadata.yaml" \
        == util.change_url_filename(
            "https://github.com/declarativesystems/ringmaster/tree/master/examples/aws/eks-cluster",
            "metadata.yaml",
        )


def test_get_processed_filename():
    """template output is stored in the .processed directory, per-environment,
    check filenames generated correctly"""

    assert util.get_processed_filename(".", "stack/bar/xyz.yaml", None) == \
        ".processed/stack/bar/xyz.yaml"

    assert util.get_processed_filename(".", "stack/bar/xyz.yaml", "dev") == \
        ".processed/dev/stack/bar/xyz.yaml"

    assert util.get_processed_filename(".", "stack/bar/xyz.yaml", "dev/special") == \
        ".processed/dev/special/stack/bar/xyz.yaml"

    # absolute path is rejected
    with pytest.raises(RuntimeError):
        util.get_processed_filename("/tmp/x", "/tmp/x/xyz.yaml", None)

    # must not return input file as output file
    with pytest.raises(RuntimeError):
        util.get_processed_filename(None, "/tmp/foo/bar", None)


def test_read_yaml_file():
    """Test we can read a yaml file and raise if its missing"""
    filename = os.path.join(root_dir, ".env/databag.yaml")
    yaml_data = util.read_yaml_file(filename)
    assert yaml_data["common_value"] == "common"

    # raises on missing file
    with pytest.raises(FileNotFoundError):
        _ = util.read_yaml_file("nothere.yaml")

    # raises on empty file
    _, temp_file = tempfile.mkstemp()
    with pytest.raises(RuntimeError):
        _ = util.read_yaml_file(temp_file)

    os.unlink(temp_file)


def test_save_yaml_file():
    """Test we can save yaml data"""

    # save and read back data
    tempdir = tempfile.mkdtemp()
    data = {"avalue": "a"}
    filename = os.path.join(tempdir, "foo/foo.yaml")
    util.save_yaml_file(filename, data)
    loaded = util.read_yaml_file(filename)
    assert loaded["avalue"] == data["avalue"]

    # save and read back data
    comment = "# HELLO\n"
    tempdir = tempfile.mkdtemp()
    filename = os.path.join(tempdir, "bar/bar.yaml")
    util.save_yaml_file(filename, data, comment)
    with open(filename, "r") as f:
        file_lines = f.readlines()

    assert file_lines[0] == comment

    loaded = util.read_yaml_file(filename)
    assert loaded["avalue"] == data["avalue"]

    shutil.rmtree(tempdir)


def test_substitute_placeholders_from_file_to_file():
    """Test end-to-end template processing and output file generation"""

    # copy testcase to tempdir
    tempdir = tempfile.mkdtemp()
    relative_file = "teststack/0010-foo/test.kubectl.yaml"
    source_filename = os.path.join(root_dir, relative_file)
    input_filename = os.path.join(tempdir, relative_file)
    input_dir = os.path.dirname(input_filename)
    pathlib.Path(input_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy(source_filename, input_filename)
    processed_filename = util.get_processed_filename(tempdir, relative_file, None)

    data = {"parent_value": "top"}
    util.substitute_placeholders_from_file_to_file(
        tempdir,
        relative_file,
        "#",
        constants.UP_VERB,
        data
    )

    # target exists and is valid yaml
    yaml_data = util.read_yaml_file(processed_filename)
    assert yaml_data["parent_value"] == data["parent_value"]

    shutil.rmtree(tempdir)


def test_substitute_placeholders_from_file_to_file_env():
    """Test end-to-end template processing and output file generation with env"""

    # copy testcase to tempdir
    tempdir = tempfile.mkdtemp()
    relative_file = "teststack/0010-foo/test.kubectl.yaml"
    source_filename = os.path.join(root_dir, relative_file)
    input_filename = os.path.join(tempdir, relative_file)
    input_dir = os.path.dirname(input_filename)
    pathlib.Path(input_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy(source_filename, input_filename)

    env_name = "dev"
    data = {
        "parent_value": "override",
        constants.DATABAG_ENV_KEY: env_name
    }

    processed_filename = util.get_processed_filename(tempdir, relative_file, env_name)
    util.substitute_placeholders_from_file_to_file(
        tempdir,
        relative_file,
        "#",
        constants.UP_VERB,
        data
    )

    # target exists and is valid yaml
    yaml_data = util.read_yaml_file(processed_filename)
    assert yaml_data["parent_value"] == data["parent_value"]

    shutil.rmtree(tempdir)
