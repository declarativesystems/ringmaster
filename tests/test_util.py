import pytest
import ringmaster.util as util


def test_string_to_snakecase():
    assert "lowercase_hyphen_separated" \
           == util.string_to_snakecase("lowercase-hyphen-separated")
    assert "mixed_case_pascal_case_and_hyphen_separated" \
           == util.string_to_snakecase("mixed-CasePascalCaseAndHyphenSeparated")
