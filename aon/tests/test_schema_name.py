"""Test that AON schema names are checked before they reach DDL."""

import pytest
from geneweaver.aon.core.schema_version import checked_schema_name


@pytest.mark.parametrize(
    "name", ["v6_0_0__15_38_54_19_02_2024", "v8_0_0a1__00_00_00_01_01_2026"]
)
def test_plain_schema_names_pass(name: str) -> None:
    """The names loads have produced so far are accepted unchanged."""
    assert checked_schema_name(name) == name


@pytest.mark.parametrize(
    "name", ['v1"; DROP SCHEMA versions CASCADE; --', "v1 x", "", "v" * 64, None]
)
def test_other_schema_names_are_refused(name: str) -> None:
    """Anything but a plain identifier never reaches DDL."""
    with pytest.raises(ValueError, match="Invalid AON schema name"):
        checked_schema_name(name)
