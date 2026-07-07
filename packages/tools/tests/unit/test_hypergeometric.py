"""Tests for the HyperGeometric (Fisher's exact) tool."""

import pytest
from geneweaver.tools.framework.abstract import AbstractTool
from geneweaver.tools.hypergeometric import (
    ContingencyCounts,
    HyperGeometric,
    HyperGeometricInput,
    HyperGeometricOutput,
    fisher_exact_2x2,
)


def test_is_abstract_tool() -> None:
    """HyperGeometric implements the framework contract."""
    t = HyperGeometric()
    assert isinstance(t, AbstractTool)
    assert t.tool_input is HyperGeometricInput
    assert t.tool_output is HyperGeometricOutput
    assert t.tool_name == "HyperGeometric"


def test_odds_ratio() -> None:
    """Odds ratio = f00*f11 / (f01*f10); None when an off-diagonal cell is zero."""
    odds, *_ = fisher_exact_2x2(10, 2, 3, 8)
    assert odds == pytest.approx(10 * 8 / (2 * 3))
    assert fisher_exact_2x2(5, 0, 3, 8)[0] is None  # f01 == 0 -> infinite


def test_p_values_in_range() -> None:
    """Upper/lower/two-tailed p-values are valid probabilities."""
    _, upper, lower, two_tailed = fisher_exact_2x2(8, 2, 1, 5)
    for p in (upper, lower, two_tailed):
        assert 0.0 <= p <= 1.0


def test_two_tailed_matches_scipy() -> None:
    """The (bug-fixed) two-tailed p-value matches scipy's Fisher exact."""
    stats = pytest.importorskip("scipy.stats")
    table = (8, 2, 1, 5)  # f00, f01, f10, f11
    _, _, _, two_tailed = fisher_exact_2x2(*table)
    f00, f01, f10, f11 = table
    expected = stats.fisher_exact([[f00, f01], [f10, f11]], alternative="two-sided")[1]
    assert two_tailed == pytest.approx(expected, rel=1e-9)


def test_run_derives_hypergeometric() -> None:
    """run() returns a result per pair with the legacy hg derivation."""
    out = HyperGeometric().run(
        HyperGeometricInput(
            geneset_ids=["GS1", "GS2"],
            pairs=[ContingencyCounts(i=0, j=1, f00=8, f01=2, f10=1, f11=5)],
        )
    )
    assert isinstance(out, HyperGeometricOutput)
    (r,) = out.results
    # odds ratio = 8*5/(2*1) = 20 > 1 -> hg = 1 - upper_tail
    assert r.odds_ratio == pytest.approx(20.0)
    assert r.hypergeometric == pytest.approx(1.0 - r.upper_tail)
