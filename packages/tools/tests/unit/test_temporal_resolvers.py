"""Tests for resolving large tool input from the database (G3-784).

MSET's background is the full gene space for a species -- ~100,000 identifiers, which
measured 1.8-2.7 MiB once encoded and so could not travel through Temporal. A request now
carries a reference and the activity expands it here.
"""

from unittest.mock import patch

import pytest
from geneweaver.tools.temporal.resolvers import (
    UNIVERSE_KEY,
    needs_resolution,
    resolve_input,
    resolve_mset_input,
)

UNIVERSE = ["Abca1", "Brca2", "Cdk2"]


class FakeCursor:
    """Returns canned rows; the queries themselves are covered in packages/db."""

    def __init__(self, universe: list[str], species: dict[int, int]) -> None:
        self._universe = universe
        self._species = species

    def execute(self, sql: str, params: dict | None = None) -> None:
        """Record the query so `fetchall` can answer the right shape."""
        self._sql = sql
        self._params = params or {}

    def fetchall(self) -> list:
        """Canned rows, keyed off which table the last query named."""
        if "production.geneset" in self._sql:
            return [
                {"gs_id": gs_id, "sp_id": sp_id}
                for gs_id, sp_id in self._species.items()
                if gs_id in self._params.get("geneset_ids", [])
            ]
        return [{"ode_ref_id": symbol} for symbol in self._universe]


@pytest.fixture
def cursor() -> FakeCursor:
    """A cursor with three gene sets: 101 and 102 in species 1, 103 in species 2."""
    return FakeCursor(UNIVERSE, {101: 1, 102: 1, 103: 2})


def test_an_explicit_species_resolves_both_backgrounds(cursor: FakeCursor) -> None:
    """One universe serves both groups: same species, same identifier space."""
    resolved = resolve_mset_input(cursor, {"group_1_genes": ["Abca1"]}, {"species_id": 1})

    assert resolved["group_1_background"] == UNIVERSE
    assert resolved["group_2_background"] == UNIVERSE
    assert resolved["group_1_genes"] == ["Abca1"], "existing input must be preserved"


def test_the_species_can_be_derived_from_the_gene_sets(cursor: FakeCursor) -> None:
    """The API and UI hold gene set ids, not species ids."""
    resolved = resolve_mset_input(cursor, {}, {"geneset_ids": [101, 102]})
    assert resolved["group_1_background"] == UNIVERSE


def test_gene_sets_from_different_species_are_refused(cursor: FakeCursor) -> None:
    """A shared background cannot represent two gene spaces; legacy refused this too."""
    with pytest.raises(ValueError, match="different species"):
        resolve_mset_input(cursor, {}, {"geneset_ids": [101, 103]})


def test_an_unknown_gene_set_is_refused(cursor: FakeCursor) -> None:
    """A typo in a gene set id must not silently pick a species."""
    with pytest.raises(ValueError, match=r"No such gene set\(s\): \[999\]"):
        resolve_mset_input(cursor, {}, {"geneset_ids": [101, 999]})


@pytest.mark.parametrize(
    "reference",
    [{}, {"species_id": None}, {"geneset_ids": []}],
    ids=["empty", "null-species", "empty-genesets"],
)
def test_an_empty_reference_is_refused(cursor: FakeCursor, reference: dict) -> None:
    """A reference naming nothing cannot select a universe."""
    with pytest.raises(ValueError, match=r"species_id.*geneset_ids"):
        resolve_mset_input(cursor, {}, reference)


@pytest.mark.parametrize(
    "reference",
    [{"species_id": "1"}, {"species_id": 1.5}, {"species_id": True}],
    ids=["string", "float", "bool"],
)
def test_a_non_integer_species_is_refused(cursor: FakeCursor, reference: dict) -> None:
    """`True` included: it is an int in Python but never a species."""
    with pytest.raises(ValueError, match="must be an integer"):
        resolve_mset_input(cursor, {}, reference)


def test_non_integer_geneset_ids_are_refused(cursor: FakeCursor) -> None:
    """String ids would not match the integer column."""
    with pytest.raises(ValueError, match="list of integers"):
        resolve_mset_input(cursor, {}, {"geneset_ids": ["101"]})


def test_a_species_with_no_genes_is_refused() -> None:
    """Better than handing MSETcpp an empty background and letting it abort."""
    empty = FakeCursor([], {101: 9})
    with pytest.raises(ValueError, match="no background to sample from"):
        resolve_mset_input(empty, {}, {"species_id": 9})


def test_an_explicit_background_is_not_overridden(cursor: FakeCursor) -> None:
    """A caller that already resolved the universe -- the in-process API -- wins."""
    resolved = resolve_mset_input(
        cursor, {"group_1_background": ["Mine"], "group_2_background": ["Also"]}, {"species_id": 1}
    )
    assert resolved["group_1_background"] == ["Mine"]
    assert resolved["group_2_background"] == ["Also"]


class TestWhenResolutionRuns:
    """Resolution must not open a connection for tools that do not need one."""

    def test_a_tool_with_no_resolver_needs_none(self) -> None:
        """Only tools in the registry resolve anything."""
        assert not needs_resolution("upset", {UNIVERSE_KEY: {"species_id": 1}})

    def test_mset_without_a_reference_needs_none(self) -> None:
        """Inline backgrounds remain valid -- the reference is an alternative, not a rule."""
        assert not needs_resolution("mset", {"input": {"group_1_background": ["A"]}})

    def test_mset_with_a_reference_needs_resolution(self) -> None:
        """A reference is the signal to open a connection."""
        assert needs_resolution("mset", {UNIVERSE_KEY: {"species_id": 1}})

    def test_no_database_is_opened_when_nothing_needs_resolving(self) -> None:
        """The python-profile worker has no database settings at all."""
        with patch("geneweaver.tools.temporal.db.cursor") as db_cursor:
            result = resolve_input("upset", {"input": {"geneset_ids": ["1"]}})
        db_cursor.assert_not_called()
        assert result == {"geneset_ids": ["1"]}

    def test_the_database_is_opened_when_a_reference_is_present(self, cursor: FakeCursor) -> None:
        """And the resolved universe reaches the tool input."""
        with patch("geneweaver.tools.temporal.db.cursor") as db_cursor:
            db_cursor.return_value.__enter__.return_value = cursor
            result = resolve_input("mset", {"input": {}, UNIVERSE_KEY: {"species_id": 1}})
        db_cursor.assert_called_once()
        assert result["group_1_background"] == UNIVERSE
