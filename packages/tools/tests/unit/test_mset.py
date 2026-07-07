"""Tests for the MSET tool (wraps the MSET C++ binary via an injectable runner)."""

import pytest
from geneweaver.tools.framework.abstract import AbstractTool
from geneweaver.tools.mset import (
    MSET,
    MSETInput,
    MSETOutput,
    intersect_genes,
    parse_tsv_dict,
)


def test_is_abstract_tool() -> None:
    """MSET implements the framework contract."""
    t = MSET(runner=lambda *a: ("", ""))
    assert isinstance(t, AbstractTool)
    assert t.tool_input is MSETInput
    assert t.tool_output is MSETOutput
    assert t.tool_name == "MSET"


def test_intersect_genes_order_and_dedup() -> None:
    """Intersection preserves group-1 order and deduplicates."""
    assert intersect_genes(["a", "b", "c", "b"], ["b", "c", "x"]) == ["b", "c"]


def test_parse_tsv_dict() -> None:
    """TSV key/value lines parse into a dict; blank lines ignored."""
    assert parse_tsv_dict("p_value\t0.01\nmean\t5\n\n") == {"p_value": "0.01", "mean": "5"}


def test_run_invokes_runner_and_parses() -> None:
    """run() passes the right args to the runner and parses both outputs."""
    captured = {}

    def fake_runner(g1, g2, bg1, bg2, n, over):
        captured["args"] = (g1, g2, bg1, bg2, n, over)
        return "p_value\t0.02\n", "0\t10\n1\t5\n"

    out = MSET(runner=fake_runner).run(
        MSETInput(
            group_1_genes=["a", "b"],
            group_2_genes=["b", "c"],
            group_1_background="bg1.txt",
            group_2_background="bg2.txt",
            number_of_samples=500,
            over_representation=True,
        )
    )
    assert isinstance(out, MSETOutput)
    # group_2 correctly uses its own background (legacy bug fixed)
    assert captured["args"] == (["a", "b"], ["b", "c"], "bg1.txt", "bg2.txt", 500, True)
    assert out.intersect_genes == ["b"]
    assert out.mset_data == {"p_value": "0.02"}
    assert out.mset_hist == {"0": "10", "1": "5"}


def test_unconfigured_binary_raises() -> None:
    """Without a runner or binary path, running raises a helpful error."""
    with pytest.raises(RuntimeError, match="MSET binary not configured"):
        MSET().run(
            MSETInput(
                group_1_genes=["a"],
                group_2_genes=["a"],
                group_1_background="bg1.txt",
                group_2_background="bg2.txt",
            )
        )
