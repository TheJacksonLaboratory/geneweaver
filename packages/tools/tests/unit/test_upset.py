"""Tests for the UpSet tool (gene-set intersection sizes)."""

from geneweaver.tools.framework.abstract import AbstractTool
from geneweaver.tools.upset import UpSet, UpSetInput, UpSetOutput, intersection_sizes

# gene 'a' only in GS1; 'b' in GS1 & GS2; 'c','d' only in GS2.
MEMBERSHIPS = {"GS1": ["a", "b"], "GS2": ["b", "c", "d"]}


def test_is_abstract_tool() -> None:
    """UpSet implements the framework contract."""
    t = UpSet()
    assert isinstance(t, AbstractTool)
    assert t.tool_input is UpSetInput
    assert t.tool_output is UpSetOutput
    assert t.tool_name == "UpSet"


def test_intersection_sizes() -> None:
    """Genes are counted by the exact combination of gene sets they belong to."""
    sizes = {tuple(i.genesets): i.size for i in intersection_sizes(MEMBERSHIPS)}
    assert sizes[("GS1",)] == 1  # 'a'
    assert sizes[("GS2",)] == 2  # 'c', 'd'
    assert sizes[("GS1", "GS2")] == 1  # 'b'


def test_include_zeros_only_adds_missing_combinations() -> None:
    """include_zeros fills in combinations with no genes; observed ones keep their size."""
    base = {tuple(i.genesets): i.size for i in intersection_sizes(MEMBERSHIPS)}
    withz = {
        tuple(i.genesets): i.size for i in intersection_sizes(MEMBERSHIPS, include_zeros=True)
    }
    assert base == {k: v for k, v in withz.items() if v != 0} or all(
        withz[k] == base.get(k, 0) for k in base
    )
    # all 3 non-empty combinations of 2 sets present
    assert set(withz) == {("GS1",), ("GS2",), ("GS1", "GS2")}


def test_run() -> None:
    """run() returns intersections sorted by descending size."""
    out = UpSet().run(UpSetInput(geneset_ids=["GS1", "GS2"], gene_memberships=MEMBERSHIPS))
    assert isinstance(out, UpSetOutput)
    sizes = [i.size for i in out.intersections]
    assert sizes == sorted(sizes, reverse=True)
    assert sum(sizes) == 4  # a, b, c, d
