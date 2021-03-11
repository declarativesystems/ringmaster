import pytest
import ringmaster.util as util
import os
from jinja2.exceptions import UndefinedError
import ringmaster.constants

def test_string_to_snakecase():
    assert "lowercase_hyphen_separated" \
           == util.string_to_snakecase("lowercase-hyphen-separated")
    assert "mixed_case_pascal_case_and_hyphen_separated" \
           == util.string_to_snakecase("mixed-CasePascalCaseAndHyphenSeparated")


def test_resolve_replacement_token():
    data = {
        "atoken": "avalue",
    }
    assert "avalue" == util.substitute_placeholders_from_memory_to_memory(
        ["{{atoken}}"],
        ringmaster.constants.UP_VERB,
        data
    )

    # raise on missing token
    with pytest.raises(UndefinedError):
        util.substitute_placeholders_from_memory_to_memory(
            ["{{nohere}}"],
            ringmaster.constants.UP_VERB,
            data
        )

    # no raise on missing token if going down
    util.substitute_placeholders_from_memory_to_memory(
        ["{{nohere}}"],
        ringmaster.constants.DOWN_VERB,
        data
    )


def test_resolve_env():
    value = "avalue"

    # environment variables should be automatically resolveable via
    # `{{env.NAME}}`
    os.environ["x"] = value

    assert value == util.substitute_placeholders_from_memory_to_memory(
        ["{{env.x}}"],
        ringmaster.constants.UP_VERB,
        {},
    )

    with pytest.raises(UndefinedError):
        assert value == util.substitute_placeholders_from_memory_to_memory(
            ["{{env.nothere}}"],
            ringmaster.constants.UP_VERB,
            {},
        )


def test_change_url_filename():
    assert "https://github.com/declarativesystems/ringmaster/tree/master/examples/aws/eks-cluster/metadata.yaml" \
        == util.change_url_filename(
            "https://github.com/declarativesystems/ringmaster/tree/master/examples/aws/eks-cluster",
            "metadata.yaml",
        )
