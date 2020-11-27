import pytest
import ringmaster.util as util
import os

def test_string_to_snakecase():
    assert "lowercase_hyphen_separated" \
           == util.string_to_snakecase("lowercase-hyphen-separated")
    assert "mixed_case_pascal_case_and_hyphen_separated" \
           == util.string_to_snakecase("mixed-CasePascalCaseAndHyphenSeparated")


def test_resolve_token_pipe():
    value = "avalue"
    value_base64 = util.base64encode(value)
    data = {
        "atoken": value
    }
    assert value == util.resolve_replacement_token("atoken", data)
    assert value_base64 == util.resolve_replacement_token("atoken|base64", data)

    # raise on missing token
    with pytest.raises(KeyError):
        util.resolve_replacement_token("nothere", data)

    # raise on missing function
    with pytest.raises(KeyError):
        util.resolve_replacement_token("atoken|nothere", data)

def test_resolve_token_value_simple():
    value = "avalue"
    data = {
        "atoken": value
    }
    assert value == util.resolve_token_value("atoken", data)

    os.environ["anenvironmentvar"] = value
    assert value == util.resolve_token_value("env(anenvironmentvar)", data)

    with pytest.raises(KeyError):
        util.resolve_token_value("nothere", data)

    with pytest.raises(KeyError):
        util.resolve_token_value("env(nothere)", data)

def test_resolve_token_value_string_literals():
    data = {
        "atoken": "avalue",
        "another_token": "someother",
    }

    os.environ["anenvironmentvar"] = "hello"

    # simple token lookup joined by string literal
    assert "avalue:someother" == util.resolve_token_value("atoken':'another_token", data)

    # string literal and no data lookup
    assert "a" == util.resolve_token_value("'a'", data)

    # string literal with backslash and no data lookup
    assert "'" == util.resolve_token_value("'\\''", data)

    # string literal with multiple backslashes and no data lookup
    assert "'a' 'b'" == util.resolve_token_value("'\\'a\\' \\'b\\''", data)


    # simple token lookup joined by string literal with backslash
    assert "avalue:'someother" == util.resolve_token_value("atoken':\\''another_token", data)

    # token lookup and function resolution joined by string literal
    assert "avalue:hello" == util.resolve_token_value("atoken':'env(anenvironmentvar)", data)

    # token lookup and function resolution joined by string literal containing backslash
    assert "avalue'hello" == util.resolve_token_value("atoken'\\''env(anenvironmentvar)", data)

    # simple token replacement with leading string literal
    assert ":avalue:avalue" == util.resolve_token_value("':'atoken':'atoken", data)

    # simple token replacement with trailing string literal
    assert "avalue:avalue:" == util.resolve_token_value("atoken':'atoken':'", data)

    # simple token replacement with leading and trailing string literal
    assert ":avalue:avalue:" == util.resolve_token_value("':'atoken':'atoken':'", data)

    # random stray quote should error
    with pytest.raises(KeyError):
        util.resolve_token_value("atoken'", data)


def test_resolve_env():
    value = "avalue"
    os.environ["anenvironmentvar"] = value

    assert value == util.resolve_env("anenvironmentvar")

    with pytest.raises(KeyError):
        assert value == util.resolve_env("nothere")


def test_resolve_rnf():
    fn, replacement_token_name = util.resolve_rfn("env(anenvironmentvar)")
    assert "env" == fn
    assert "anenvironmentvar" == replacement_token_name

    fn, replacement_token_name = util.resolve_rfn("adatabagvalue")
    assert fn is None
    assert "adatabagvalue" == replacement_token_name

    with pytest.raises(RuntimeError):
        util.resolve_rfn("env(notallowed(no))")

def test_substitute_placeholders_line():
    no_subst = "a line ! $ { axb llala"
    assert no_subst == util.substitute_placeholders_line(no_subst, {})

    data = {
        "avalue": "thing",
    }
    subst = "some${avalue}"
    assert "something" == util.substitute_placeholders_line(subst, data)