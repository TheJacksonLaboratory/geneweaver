"""Tests for the Jaccard Similarity tool (ported from legacy JaccardSimilarity)."""

import pytest
from geneweaver.tools.framework.abstract import AbstractTool
from geneweaver.tools.jaccard_similarity import (
    GenesetPairCounts,
    JaccardDistribution,
    JaccardSimilarity,
    JaccardSimilarityInput,
    JaccardSimilarityOutput,
    empirical_p_value,
    jaccard_coefficient,
)

# Null distribution for two size-3 sets: (jaccard_value, frequency)
DIST_3_3 = JaccardDistribution(
    set_size1=3, set_size2=3, homology=False, frequencies=[(0.1, 10), (0.4, 5), (0.6, 2)]
)


def test_is_abstract_tool() -> None:
    """JaccardSimilarity implements the framework contract."""
    t = JaccardSimilarity()
    assert isinstance(t, AbstractTool)
    assert t.tool_input is JaccardSimilarityInput
    assert t.tool_output is JaccardSimilarityOutput
    assert t.tool_name == "JaccardSimilarity"


def test_jaccard_coefficient() -> None:
    """J = C / (A + B + C); 0 when no intersection."""
    assert jaccard_coefficient(3, 3, 4) == pytest.approx(0.4)
    assert jaccard_coefficient(5, 5, 0) == 0.0
    assert jaccard_coefficient(0, 0, 7) == 1.0  # identical sets


def test_empirical_p_value_counts_tail() -> None:
    """p = (1 + freq with jac >= observed) / (1 + total freq)."""
    dists = {(3, 3, False): DIST_3_3.frequencies}
    # A=3, B=3, C=4 -> N=10, J=0.4. tail (jac>=0.4): 5+2=7 -> (1+7)/(1+17) = 8/18
    p = empirical_p_value(3, 3, 4, dists, homology=False)
    assert p == pytest.approx(8 / 18)


def test_empirical_p_value_identical_sets_is_one() -> None:
    """A==0 and B==0 (identical sets) -> p = 1.0."""
    assert empirical_p_value(0, 0, 5, {}, homology=False) == 1.0


def test_empirical_p_value_missing_distribution_is_zero() -> None:
    """No distribution available -> 0.0 (legacy fell back to generating it)."""
    assert empirical_p_value(3, 3, 4, {}, homology=False) == 0.0


def test_set_sizes_are_sorted_for_lookup() -> None:
    """A>B is swapped so the (small,large) distribution key is used."""
    dists = {(3, 5, False): [(0.5, 4)]}
    # pass A=5, B=3 -> should look up (3,5)
    p = empirical_p_value(5, 3, 2, dists, homology=False)
    assert p == pytest.approx((1 + 4) / (1 + 4))  # J=2/10=0.2 <= 0.5 so tail includes it


def test_run_produces_per_pair_results() -> None:
    """run() returns a result per pair, with p_value None for empty intersections."""
    out = JaccardSimilarity().run(
        JaccardSimilarityInput(
            geneset_ids=["GS1", "GS2", "GS3"],
            include_homology=False,
            pairs=[
                GenesetPairCounts(i=0, j=1, only_i=3, only_j=3, intersection=4),
                GenesetPairCounts(i=0, j=2, only_i=5, only_j=5, intersection=0),
            ],
            distributions=[DIST_3_3],
        )
    )
    assert isinstance(out, JaccardSimilarityOutput)
    assert len(out.results) == 2
    r01, r02 = out.results
    assert r01.jaccard == pytest.approx(0.4)
    assert r01.p_value == pytest.approx(8 / 18)
    # no intersection -> jaccard 0, p_value None
    assert r02.jaccard == 0.0
    assert r02.p_value is None
