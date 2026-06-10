"""Tests for the PhenomeMap tool (wraps the biclique C binary via an injectable runner)."""

import pytest
from geneweaver.tools.framework.abstract import AbstractTool
from geneweaver.tools.phenome_map import (
    PhenomeMap,
    PhenomeMapInput,
    PhenomeMapOutput,
    build_edge_list,
    compute_subset_links,
    find_cut_depth,
    parse_bicliques,
)
from geneweaver.tools.phenome_map.tool import _Biclique

# A fake biclique-binary stdout: 3 lines per biclique (gene-sets, genes, blank).
# A {GS1,GS2,GS3}/{g1,g2}  >  B {GS1,GS2}/{g1,g2,g4}  >  C {GS1}/{g1,g2,g3,g4}
FAKE_BICLIQUE_OUTPUT = "GS1\tGS2\tGS3\ng1\tg2\n\nGS1\tGS2\ng1\tg2\tg4\n\nGS1\ng1\tg2\tg3\tg4\n\n"


def _tool(output: str = FAKE_BICLIQUE_OUTPUT) -> PhenomeMap:
    return PhenomeMap(biclique_runner=lambda _edge_list: output)


def test_is_abstract_tool() -> None:
    """PhenomeMap implements the framework contract."""
    t = _tool()
    assert isinstance(t, AbstractTool)
    assert t.tool_input is PhenomeMapInput
    assert t.tool_output is PhenomeMapOutput
    assert t.tool_name == "PhenomeMap"


def test_build_edge_list() -> None:
    """Edge list has the count header then one gene/gene-set edge per membership."""
    text, num_genes, num_genesets = build_edge_list({"GS1": ["g1", "g2"], "GS2": ["g2"]})
    lines = text.splitlines()
    # 2 distinct genes (g1, g2), 2 gene sets, 3 edges (g1-GS1, g2-GS1, g2-GS2).
    assert lines[0] == "2\t2\t3"
    assert (num_genes, num_genesets) == (2, 2)
    assert set(lines[1:]) == {"g1\tGS1", "g2\tGS1", "g2\tGS2"}


def test_parse_bicliques() -> None:
    """The 3-line-per-biclique stdout decodes into (gene-sets, genes) pairs."""
    parsed = parse_bicliques(FAKE_BICLIQUE_OUTPUT)
    assert len(parsed) == 3
    assert parsed[0] == (frozenset({"GS1", "GS2", "GS3"}), ["g1", "g2"])
    assert parsed[2] == (frozenset({"GS1"}), ["g1", "g2", "g3", "g4"])


def test_run_builds_nested_graph() -> None:
    """run() links each biclique to its immediate descendant (transitive reduction)."""
    out = _tool().run(PhenomeMapInput(gene_sets={"GS1": ["g1"], "GS2": ["g1"], "GS3": ["g1"]}))
    assert isinstance(out, PhenomeMapOutput)
    by_id = {n.id: n for n in out.nodes}
    assert len(by_id) == 3

    # A (3 gene sets) is the root at depth 0; C (1 gene set) is the leaf, deepest.
    root = next(n for n in out.nodes if n.depth == 0)
    assert root.genesets == ["GS1", "GS2", "GS3"]
    assert [child.target for child in root.children] == [
        n.id for n in out.nodes if n.genesets == ["GS1", "GS2"]
    ]

    # The middle node parents the leaf; the leaf has no children, only a parent.
    leaf = next(n for n in out.nodes if n.genesets == ["GS1"])
    assert leaf.children == []
    assert leaf.parents  # has a parent
    assert leaf.depth == 2


def test_run_scores_links_by_gene_ratio_without_ranks() -> None:
    """Without ranks the link score is the parent/child gene-count ratio."""
    out = _tool().run(PhenomeMapInput(gene_sets={"GS1": ["g1"]}))
    root = next(n for n in out.nodes if n.depth == 0)  # 2 genes
    mid_id = root.children[0].target
    # parent (A) has 2 genes, child (B) has 3 -> 2/3
    assert root.children[0].score == pytest.approx(2 / 3)
    mid = next(n for n in out.nodes if n.id == mid_id)
    # B has 3 genes, C has 4 -> 3/4
    assert mid.children[0].score == pytest.approx(3 / 4)


def test_min_genes_filters_small_bicliques() -> None:
    """Bicliques with fewer than min_genes genes are dropped."""
    out = _tool().run(PhenomeMapInput(gene_sets={"GS1": ["g1"]}, min_genes=3))
    # A has only 2 genes -> dropped; B(3) and C(4) remain and stay linked.
    assert all(len(n.genes) >= 3 for n in out.nodes)
    assert {tuple(n.genesets) for n in out.nodes} == {("GS1", "GS2"), ("GS1",)}


def test_emphasis_flag() -> None:
    """Only bicliques containing an emphasis gene are flagged."""
    out = _tool().run(PhenomeMapInput(gene_sets={"GS1": ["g1"]}, emphasis_genes=["g3"]))
    # g3 only appears in C ({GS1}); A and B do not contain it.
    emphasized = {tuple(n.genesets) for n in out.nodes if n.emphasize}
    assert emphasized == {("GS1",)}


def test_pvalue_trim_removes_high_score_links() -> None:
    """A strict threshold drops links scoring above it, leaving unconnected nodes trimmed."""
    out = _tool().run(PhenomeMapInput(gene_sets={"GS1": ["g1"]}, p_value_threshold=0.7))
    # A->B scores 2/3~=0.667 (kept, <=0.7); B->C scores 0.75 (removed, >0.7).
    # C then has no parent/child link and is trimmed out.
    assert all(n.genesets != ["GS1"] for n in out.nodes)
    assert any(n.genesets == ["GS1", "GS2", "GS3"] for n in out.nodes)


def test_no_bicliques_returns_note() -> None:
    """Empty biclique output yields no nodes and an explanatory note."""
    out = PhenomeMap(biclique_runner=lambda _e: "").run(PhenomeMapInput(gene_sets={"GS1": ["g1"]}))
    assert out.nodes == []
    assert out.notes


def test_find_cut_depth_no_max_level() -> None:
    """max_level=0 disables cutting (cut_depth 0, counts everything)."""
    by_size = [
        (1, [_Biclique(1, frozenset({"a"}), ["g"], [])]),
        (2, [_Biclique(2, frozenset({"a", "b"}), ["g"], [])]),
    ]
    total, cut = find_cut_depth(by_size, max_level=0)
    assert (total, cut) == (2, 0)


def test_compute_subset_links_transitive_reduction() -> None:
    """A only links to its immediate child B, not to B's child C."""
    c = _Biclique(1, frozenset({"a"}), ["g1"], [])
    b = _Biclique(2, frozenset({"a", "b"}), ["g1", "g2"], [])
    a = _Biclique(3, frozenset({"a", "b", "c"}), ["g1"], [])
    compute_subset_links([(1, [c]), (2, [b]), (3, [a])])
    assert set(a.children) == {b.id}  # not c
    assert set(b.children) == {c.id}
    assert set(c.parents) == {b.id}


def test_unconfigured_binary_raises() -> None:
    """Without a runner or binary path, running raises a helpful error."""
    with pytest.raises(RuntimeError, match="biclique binary not configured"):
        PhenomeMap().run(PhenomeMapInput(gene_sets={"GS1": ["g1"]}))


def test_cut_does_not_leave_dangling_links() -> None:
    """After a level is cut, surviving nodes must not emit links to trimmed nodes."""
    # Two size-2 bicliques (a level with >max_level nodes) under one size-4 root, plus a
    # size-1 leaf. max_level=1 cuts everything of size <= 2, leaving only the root, whose
    # child links pointed into the cut level.
    output = (
        "G1\tG2\tG3\tG4\nx\n\n"
        "G1\tG2\nx\ta\tb\n\n"
        "G3\tG4\nx\tc\td\n\n"
        "G1\nx\ta\tb\te\n\n"
    )
    out = PhenomeMap(biclique_runner=lambda _e: output).run(
        PhenomeMapInput(gene_sets={"G1": ["x"]}, max_level=1)
    )
    ids = {n.id for n in out.nodes}
    assert out.cut_depth == 2
    for n in out.nodes:
        assert all(link.target in ids for link in n.children)
        assert all(pid in ids for pid in n.parents)


def test_bootstrap_runner_invoked_on_large_graph() -> None:
    """A bootstrap runner is called past the node threshold and sets displayed flags."""
    calls = {}

    def fake_bootstrap(bic_text):
        calls["bic"] = bic_text
        # Mark only the indices of the displayed bicliques (all three here).
        return {0, 1, 2}, {}

    out = PhenomeMap(
        biclique_runner=lambda _e: FAKE_BICLIQUE_OUTPUT,
        bootstrap_runner=fake_bootstrap,
    ).run(PhenomeMapInput(gene_sets={"GS1": ["g1"]}, bootstrap_node_threshold=1))
    assert "bic" in calls  # bootstrap ran
    assert out.bootstrap_applied is True
    assert all(n.displayed for n in out.nodes)
