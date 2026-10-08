"""Tests for the pure per-tool input builders.

These derive everything from memberships already fetched, so they need no database and the
arithmetic is checkable by hand -- which matters, because a wrong contingency table or
similarity matrix produces a plausible-looking but incorrect statistic rather than an error.
"""

from typing import ClassVar

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


class TestPairwiseDeletion:
    """Legacy pairwise deletion: count only what both platforms could have measured."""

    # 10 and 11 are mouse platforms; 20 is a human one; -7 is a gene-symbol set.
    PLATFORMS: ClassVar = {1: (1, 10), 2: (1, 11), 3: (1, 10), 4: (2, 20), 5: (1, -7)}
    GENES: ClassVar = {10: {"x", "y", "z", "w", "v"}, 11: {"y", "z", "q"}, 20: {"x"}}

    def test_only_same_species_platform_pairs_need_platform_genes(self) -> None:
        """A run of gene-identifier sets, or of two species, queries no platform."""
        assert tool_inputs.deletion_platforms([1, 2, 4, 5], self.PLATFORMS) == {10, 11}
        assert tool_inputs.deletion_platforms([1, 4, 5], self.PLATFORMS) == set()

    def test_scopes_follow_legacy_rules(self) -> None:
        """Different platforms: their shared genes. Same platform: no restriction."""
        scopes = tool_inputs.pairwise_deletion_scopes([1, 2, 3, 4, 5], self.PLATFORMS, self.GENES)
        assert scopes[(0, 1)] == tool_inputs.PairScope(frozenset({"y", "z"}), 2)
        assert scopes[(0, 2)] == tool_inputs.PairScope(None, 5)
        # Other species, or a gene-symbol set: counted normally, so no entry.
        assert (0, 3) not in scopes
        assert (0, 4) not in scopes

    def test_jaccard_counts_only_genes_both_platforms_measure(self) -> None:
        """'x' is on platform 10 only, so it cannot count against set 2."""
        memberships = {"1": ["x", "y", "z"], "2": ["y", "z", "w"]}
        scopes = {(0, 1): tool_inputs.PairScope(frozenset({"y", "z"}), 2)}
        plain = tool_inputs.jaccard_pair_counts(memberships, [1, 2])[0]
        deleted = tool_inputs.jaccard_pair_counts(memberships, [1, 2], scopes)[0]
        assert (plain["only_i"], plain["only_j"], plain["intersection"]) == (1, 1, 2)
        assert (deleted["only_i"], deleted["only_j"], deleted["intersection"]) == (0, 0, 2)

    def test_hypergeometric_population_is_the_platforms(self) -> None:
        """Same platform: every gene counts, but f00 is the platform's other genes."""
        memberships = {"1": ["x", "y"], "2": ["y", "z"]}
        scopes = {(0, 1): tool_inputs.PairScope(None, 100)}
        table = tool_inputs.contingency_pairs(memberships, [1, 2], scopes)[0]
        assert (table["f11"], table["f10"], table["f01"], table["f00"]) == (1, 1, 1, 97)

    def test_homology_merged_members_count_if_any_symbol_is_measurable(self) -> None:
        """A merged "A/B" member is on the platform when either symbol is."""
        memberships = {"1": ["DRD2/Drd2", "x"], "2": ["DRD2/Drd2"]}
        scopes = {(0, 1): tool_inputs.PairScope(frozenset({"Drd2"}), 1)}
        counts = tool_inputs.jaccard_pair_counts(memberships, [1, 2], scopes)[0]
        assert (counts["only_i"], counts["only_j"], counts["intersection"]) == (0, 0, 1)
        table = tool_inputs.contingency_pairs(memberships, [1, 2], scopes)[0]
        assert table["f00"] == 0
