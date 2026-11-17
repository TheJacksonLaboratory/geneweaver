"""Triclique (legacy TricliqueViewer) and its port of the ``bk-partite`` search.

The port was checked against the compiled binary (``TOOLBOX/bk-partite``, built with gcc 12)
on 475 graphs -- 500 random pairs of groups and real dev gene sets, less those with no
edges: the maximal clique count and both kept cliques, members in the binary's order,
agreed in every one. `BINARY_CASES` pins three of them where the vertex and edge maxima
differ, with the binary's own output.
"""

import pytest
from geneweaver.tools.triclique import TricliqueInput, TricliqueTool, kpartite, tripartite_edges
from geneweaver.tools.triclique.schema import MAX_SHARED_GENES
from pydantic import ValidationError

#: (group A size, memberships, binary's "No. of k-cliques", vertex maximum, edge maximum).
BINARY_CASES = {
    "rand001": (
        6,
        {
            "a0": ["g0"],
            "a1": ["g0", "own_a1"],
            "a2": ["g0", "own_a2"],
            "a3": ["g0", "g1"],
            "a4": ["g1"],
            "a5": ["g0", "g1"],
            "b0": ["g0", "g1"],
            "b1": ["g1"],
        },
        3,
        [["a3", "a5", "a1", "a2", "a0"], ["b0"], ["g0"]],
        [["a3", "a5", "a4"], ["b0", "b1"], ["g1"]],
    ),
    "rand009": (
        5,
        {
            "a0": ["g1", "g2", "g3", "own_a0"],
            "a1": ["g0", "g1", "g2", "g3"],
            "a2": [],
            "a3": ["g0", "g1", "g3"],
            "a4": ["g1"],
            "b0": ["g2"],
            "b1": [],
            "b2": ["g2", "g3", "own_b2"],
            "b3": ["g0", "g1"],
            "b4": ["g2", "g3"],
            "b5": ["own_b5"],
        },
        5,
        [["a1", "a0", "a3", "a4"], ["b3"], ["g1"]],
        [["a1", "a0"], ["b4", "b2"], ["g2", "g3"]],
    ),
    "rand017": (
        4,
        {
            "a0": ["g1", "g2", "g3", "g4", "g5", "g6", "own_a0"],
            "a1": ["g1", "g3", "g4", "g5", "g6", "g8"],
            "a2": ["g1", "g2", "g3", "g4", "g5", "g6", "g8", "g9", "own_a2"],
            "a3": ["g2", "g5", "g6", "g7", "g8", "g9"],
            "b0": ["g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8", "own_b0"],
        },
        9,
        [["a2", "a0"], ["b0"], ["g5", "g6", "g1", "g3", "g4", "g2"]],
        [["a1", "a2", "a0"], ["b0"], ["g5", "g6", "g1", "g3", "g4"]],
    ),
}


def _input(size_a: int, memberships: dict[str, list[str]], **options) -> TricliqueInput:
    ids = list(memberships)
    return TricliqueInput(
        group_a=ids[:size_a], group_b=ids[size_a:], gene_memberships=memberships, **options
    )


@pytest.mark.parametrize("name", sorted(BINARY_CASES))
def test_the_search_finds_what_the_binary_finds(name: str) -> None:
    """Same count of maximal cliques, same two kept cliques, members in the same order."""
    size_a, memberships, maximal, vertex_max, edge_max = BINARY_CASES[name]
    _, edges = tripartite_edges(_input(size_a, memberships))
    graph = kpartite.KPartiteGraph.from_edges(3, edges)
    found = kpartite.find_cliques(graph)
    assert found.maximal == maximal
    assert kpartite.by_part(graph, found.vertex_max) == vertex_max
    assert kpartite.by_part(graph, found.edge_max) == edge_max


def test_the_result_names_both_maxima_and_counts_their_links() -> None:
    """Edge maximum is legacy's result; links are |A||B| + (|A| + |B|) x genes."""
    size_a, memberships, maximal, _, _ = BINARY_CASES["rand017"]
    out = TricliqueTool().run(_input(size_a, memberships, include_homology=True))
    assert out.maximal_tricliques == maximal
    assert out.edge_maximum.group_a == ["a1", "a2", "a0"]
    assert out.edge_maximum.edges == 3 * 1 + 4 * 5
    assert out.vertex_maximum.edges == 2 * 1 + 3 * 6
    assert out.include_homology is True
    assert out.shared_genes == ["g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8"]


def test_the_third_part_is_the_genes_both_groups_hold() -> None:
    """A gene in only one group is not in the graph; nor are a set's own genes."""
    shared, edges = tripartite_edges(
        TricliqueInput(
            group_a=["1"],
            group_b=["2"],
            gene_memberships={"1": ["X", "Y", "own1"], "2": ["Y", "X", "own2"]},
        )
    )
    assert shared == ["X", "Y"]
    # A to each gene, B to each gene, then A to B because they share one.
    assert edges == [
        ((0, "1"), (2, "X")),
        ((0, "1"), (2, "Y")),
        ((1, "2"), (2, "X")),
        ((1, "2"), (2, "Y")),
        ((0, "1"), (1, "2")),
    ]


def test_groups_sharing_no_gene_find_nothing() -> None:
    """No shared gene, no edge, no triclique -- not an error."""
    out = TricliqueTool().run(
        TricliqueInput(group_a=["1"], group_b=["2"], gene_memberships={"1": ["X"], "2": ["Y"]})
    )
    assert out.shared_genes == []
    assert out.maximal_tricliques == 0
    assert out.edge_maximum is None
    assert out.vertex_maximum is None


def test_a_clique_must_reach_every_part() -> None:
    """Two gene sets of A sharing genes with each other but not with B make no triclique."""
    graph = kpartite.KPartiteGraph.from_edges(3, [((0, "a1"), (0, "a2"))])
    assert kpartite.find_cliques(graph).maximal == 0


def test_more_shared_genes_than_legacy_took_is_refused() -> None:
    """Legacy refused over 50 shared genes; so does the port, rather than run for hours."""
    genes = [f"G{i}" for i in range(MAX_SHARED_GENES + 1)]
    with pytest.raises(ValueError, match="share 51 genes"):
        tripartite_edges(
            TricliqueInput(group_a=["1"], group_b=["2"], gene_memberships={"1": genes, "2": genes})
        )


def test_a_gene_set_is_in_one_group_only() -> None:
    """The groups are the graph's first two parts, so they cannot overlap."""
    with pytest.raises(ValidationError, match="in both groups: 2"):
        TricliqueInput(group_a=["1", "2"], group_b=["2"])


def test_each_group_needs_a_gene_set() -> None:
    """Without one group there is no tripartite graph."""
    with pytest.raises(ValidationError):
        TricliqueInput(group_a=["1"], group_b=[])
