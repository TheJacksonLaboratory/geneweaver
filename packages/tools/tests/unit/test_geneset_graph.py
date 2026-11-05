"""GeneSet Graph (legacy GeneSetViewer).

Checked against legacy's own `GeneSetViewer.mainexec`, run unchanged on real dev gene sets
(three groups x minimum degree Auto/1/2/3 x suppress on/off): the drawn genes and gene sets,
the Auto degree and the degree statistics match in all 24 cases but one, a legacy bug kept
out of the port -- see `test_the_minimum_degree_statistic_is_the_genes_own`.
"""

from collections import Counter

import pytest
from geneweaver.tools.geneset_graph import GenesetGraph, GenesetGraphInput, auto_min_degree
from pydantic import ValidationError

MEMBERSHIPS = {"1": ["A", "B", "C"], "2": ["B", "C", "D"], "3": ["C", "E"], "4": ["F"]}


def _run(**options):
    return GenesetGraph().run(
        GenesetGraphInput(geneset_ids=list(MEMBERSHIPS), gene_memberships=MEMBERSHIPS, **options)
    )


def test_a_gene_is_drawn_when_enough_gene_sets_hold_it() -> None:
    """Degree is the number of gene sets holding a gene; most shared first."""
    out = _run(min_degree=2)
    assert [(g.symbol, g.degree) for g in out.genes] == [("C", 3), ("B", 2)]
    assert out.genes[0].genesets == ["1", "2", "3"]


def test_disconnected_gene_sets_are_hidden_unless_asked_for() -> None:
    """Legacy's "Suppress disconnected": On hides sets with no drawn gene."""
    assert [s.id for s in _run(min_degree=2).genesets] == ["1", "2", "3"]
    assert [s.id for s in _run(min_degree=2, suppress_disconnected=False).genesets] == [
        "1",
        "2",
        "3",
        "4",
    ]


def test_emphasis_genes_are_flagged_ignoring_case() -> None:
    """Emphasis genes are matched case-insensitively."""
    out = _run(min_degree=1, emphasis_genes=["c"])
    assert {g.symbol for g in out.genes if g.emphasized} == {"C"}


def test_degree_statistics_cover_every_gene() -> None:
    """Statistics count every gene, drawn or not, as legacy did."""
    out = _run(min_degree=3)
    assert (out.total_genes, out.min_gene_degree, out.max_gene_degree) == (6, 1, 3)
    assert out.avg_gene_degree == pytest.approx(9 / 6)


def test_the_minimum_degree_statistic_is_the_genes_own() -> None:
    """Legacy started it at the number of gene sets shown, so showed 0 when none were."""
    out = _run(min_degree=9)
    assert out.genes == []
    assert out.genesets == []
    assert out.min_gene_degree == 1


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        (Counter(), 2),  # nothing: legacy's fallback
        (Counter({1: 500, 2: 40, 3: 3, 4: 2}), 3),  # 40 at degree 2 after 5 passed -> cut above it
        (Counter({1: 500, 2: 40, 3: 30, 4: 5}), 3),  # the cut moves down: the last match wins
        (Counter({1: 500, 2: 10, 3: 3}), 2),  # no degree with more than 25
    ],
)
def test_auto_picks_the_minimum_degree_as_legacy_did(counts, expected) -> None:
    """Legacy's Auto rule, including that the last match on the way down wins."""
    assert auto_min_degree(counts) == expected


def test_auto_is_resolved_in_the_output() -> None:
    """The output says which degree Auto chose."""
    assert isinstance(_run(min_degree="auto").min_degree, int)


@pytest.mark.parametrize("bad", [0, -1, "sometimes"])
def test_a_minimum_degree_below_one_is_refused(bad) -> None:
    """Legacy's floor is 1."""
    with pytest.raises(ValidationError):
        GenesetGraphInput(gene_memberships=MEMBERSHIPS, min_degree=bad)
