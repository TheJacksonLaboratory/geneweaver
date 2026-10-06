"""Tests for the pure per-tool input builders.

These derive everything from memberships already fetched, so they need no database and the
arithmetic is checkable by hand -- which matters, because a wrong contingency table or
similarity matrix produces a plausible-looking but incorrect statistic rather than an error.
"""

import pytest

from geneweaver.api.services import tool_inputs

# a: {x, y, z}   b: {y, z, w}   c: {q}
# union (the HyperGeometric universe) = {x, y, z, w, q} -> 5
MEMBERSHIPS = {"1": ["x", "y", "z"], "2": ["y", "z", "w"], "3": ["q"]}
IDS = [1, 2, 3]


def test_memberships_keep_the_callers_order() -> None:
    """Both pairwise tools index results by position, so order is part of the contract."""
    assert tool_inputs.ordered_memberships(MEMBERSHIPS, [3, 1]) == [{"q"}, {"x", "y", "z"}]


def test_a_missing_geneset_becomes_an_empty_set() -> None:
    """A gene set that resolved to nothing must not shift the positions of the others."""
    assert tool_inputs.ordered_memberships(MEMBERSHIPS, [1, 99]) == [{"x", "y", "z"}, set()]


def test_duplicate_symbols_are_collapsed() -> None:
    """Two identifiers for one gene must not count twice -- the GWC-34 conflation."""
    assert tool_inputs.ordered_memberships({"1": ["x", "x", "y"]}, [1]) == [{"x", "y"}]


class TestContingencyPairs:
    """2x2 tables for HyperGeometric, universe = union of the requested sets."""

    def test_counts_are_correct_for_a_known_pair(self) -> None:
        """Hand-checked against the fixture above."""
        pairs = {(p["i"], p["j"]): p for p in tool_inputs.contingency_pairs(MEMBERSHIPS, IDS)}
        # a vs b: shared {y,z}=2; only-a {x}=1; only-b {w}=1; neither 5-4=1
        assert pairs[(0, 1)] == {"i": 0, "j": 1, "f11": 2, "f10": 1, "f01": 1, "f00": 1}
        # a vs c: disjoint; union is 4 of the 5-gene universe
        assert pairs[(0, 2)] == {"i": 0, "j": 2, "f11": 0, "f10": 3, "f01": 1, "f00": 1}

    def test_every_table_sums_to_the_universe(self) -> None:
        """The invariant that makes it a contingency table at all."""
        universe = len(set().union(*(set(v) for v in MEMBERSHIPS.values())))
        for pair in tool_inputs.contingency_pairs(MEMBERSHIPS, IDS):
            assert pair["f00"] + pair["f01"] + pair["f10"] + pair["f11"] == universe

    def test_one_table_per_unordered_pair(self) -> None:
        """Three gene sets give three pairs, not six or nine."""
        assert len(tool_inputs.contingency_pairs(MEMBERSHIPS, IDS)) == 3

    def test_no_pairs_for_a_single_geneset(self) -> None:
        """Nothing to compare, so no tables rather than a degenerate one."""
        assert tool_inputs.contingency_pairs(MEMBERSHIPS, [1]) == []


class TestJaccardPairCounts:
    """Overlap counts for JaccardSimilarity."""

    def test_counts_are_correct(self) -> None:
        """Hand-checked: a and b share {y, z} with one exclusive gene each."""
        counts = {(p["i"], p["j"]): p for p in tool_inputs.jaccard_pair_counts(MEMBERSHIPS, IDS)}
        assert counts[(0, 1)] == {"i": 0, "j": 1, "only_i": 1, "only_j": 1, "intersection": 2}

    def test_disjoint_sets_have_no_intersection(self) -> None:
        """Sanity check on the other direction."""
        counts = {(p["i"], p["j"]): p for p in tool_inputs.jaccard_pair_counts(MEMBERSHIPS, IDS)}
        assert counts[(0, 2)]["intersection"] == 0


class TestSimilarityMatrix:
    """Jaccard similarity matrix for JaccardClustering."""

    def test_shape_and_diagonal(self) -> None:
        """Square, and every set is perfectly similar to itself."""
        matrix = tool_inputs.similarity_matrix(MEMBERSHIPS, IDS)
        assert len(matrix) == 3
        assert all(len(row) == 3 for row in matrix)
        assert all(matrix[i][i] == 1.0 for i in range(3))

    def test_values_are_jaccard_and_symmetric(self) -> None:
        """Intersection over union, and the matrix mirrors across the diagonal."""
        matrix = tool_inputs.similarity_matrix(MEMBERSHIPS, IDS)
        # a & b: |{y,z}| / |{x,y,z,w}| = 2/4
        assert matrix[0][1] == pytest.approx(0.5)
        assert matrix[1][0] == pytest.approx(0.5)
        assert matrix[0][2] == 0.0

    def test_two_empty_sets_are_zero_not_undefined(self) -> None:
        """An empty gene set must cluster as dissimilar rather than divide by zero."""
        matrix = tool_inputs.similarity_matrix({"1": [], "2": []}, [1, 2])
        assert matrix[0][1] == 0.0
