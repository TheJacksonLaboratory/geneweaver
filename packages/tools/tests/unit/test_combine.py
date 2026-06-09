"""Tests for the Combine tool (ported from legacy toolbase.combine_genesets)."""

from geneweaver.tools.combine import Combine, CombineInput, CombineOutput
from geneweaver.tools.framework.abstract import AbstractTool

# membership rows: [gs_id, ode_gene_id, ode_ref_id]
MEMBERSHIP = [
    [10, 1, "A"],  # gene 1 in gs 10
    [11, 2, "a"],  # gene 2 in gs 11  (homolog of gene 1)
    [10, 3, "B"],  # gene 3 in gs 10
]
# homology pairs: [gene_a, gene_b]
HOMOLOGY = [[1, 2]]
# label rows: [gs_id, gs_name, gs_label]
LABELS = [[10, "Set Ten", "GS10"], [11, "Set Eleven\twith tab", "GS11"]]
GENESETS = [10, 11]


def test_is_abstract_tool() -> None:
    """Combine implements the framework contract."""
    t = Combine()
    assert isinstance(t, AbstractTool)
    assert t.tool_input is CombineInput
    assert t.tool_output is CombineOutput
    assert t.tool_name == "Combine"


def test_combine_with_homology_merges_homologs() -> None:
    """With homology on, homologous genes 1 & 2 merge into one row spanning both sets."""
    out = Combine().run(
        CombineInput(
            geneset_ids=GENESETS,
            include_homology=True,
            membership_rows=MEMBERSHIP,
            homology_pairs=HOMOLOGY,
            label_rows=LABELS,
        )
    )
    assert isinstance(out, CombineOutput)
    # gene 1 & 2 collapse to the merged row -1, which is in BOTH gene sets
    assert -1 in out.matrix
    assert out.matrix[-1][10] == 1
    assert out.matrix[-1][11] == 1
    # originals 1 and 2 are gone; gene 3 remains its own row in gs 10 only
    assert 1 not in out.matrix
    assert 2 not in out.matrix
    assert out.matrix[3][10] == 1
    assert 11 not in out.matrix[3]


def test_combine_without_homology_keeps_genes_separate() -> None:
    """With homology off, each gene stays its own row (no merge)."""
    out = Combine().run(
        CombineInput(
            geneset_ids=GENESETS,
            include_homology=False,
            membership_rows=MEMBERSHIP,
            homology_pairs=HOMOLOGY,
            label_rows=LABELS,
        )
    )
    assert set(out.matrix.keys()) == {1, 2, 3}
    assert out.matrix[1][10] == 1
    assert out.matrix[2][11] == 1
    # ode_ref_id stored under key 0
    assert out.matrix[1][0] == "A"


def test_labels_pulled_out_and_whitespace_cleaned() -> None:
    """gs labels/names are typed fields with tabs/newlines normalised to spaces."""
    out = Combine().run(
        CombineInput(geneset_ids=GENESETS, membership_rows=MEMBERSHIP, label_rows=LABELS)
    )
    assert out.gslabels == {10: "GS10", 11: "GS11"}
    assert out.gsnames[11] == "Set Eleven with tab"  # tab -> space
