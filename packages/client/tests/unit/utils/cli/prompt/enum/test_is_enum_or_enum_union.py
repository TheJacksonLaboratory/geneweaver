"""Test the is_enum_or_enum_union function."""

import pytest
from geneweaver.client.utils.cli.prompt.enum import is_enum_or_enum_union

from tests.unit.utils.cli.prompt.enum.conftest import MockEnum, MockIntEnum


@pytest.mark.parametrize("value", [MockEnum, MockIntEnum, MockEnum | MockIntEnum])
def test_is_enum_or_enum_union_with_enum(value):
    """Test the is_enum_or_enum_union function with valid input."""
    assert is_enum_or_enum_union(value)


@pytest.mark.parametrize(
    "value",
    [
        str,
        int,
        float,
        bool,
        list,
        tuple,
        dict,
        set,
        str | int,
        MockEnum | str,
        MockIntEnum | str,
    ],
)
def test_is_enum_or_enum_union_with_non_enum(value):
    """Test the is_enum_or_enum_union function with invalid input."""
    assert not is_enum_or_enum_union(value)
