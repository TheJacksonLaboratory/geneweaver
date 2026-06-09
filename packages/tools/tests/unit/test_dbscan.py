"""Tests for the DBSCAN tool (ported from legacy DBSCAN; wraps the dbscan C++ binary)."""

import json

import pytest
from geneweaver.tools.dbscan import (
    DBSCAN,
    DBSCANInput,
    DBSCANOutput,
    decode_clusters,
    encode_bipartite,
)
from geneweaver.tools.framework.abstract import AbstractTool

# 3 genes (a, b, c) across 2 gene sets.
GENE_SYMBOLS = {"GS1": ["a", "b"], "GS2": ["b", "c"]}


def test_is_abstract_tool() -> None:
    """DBSCAN implements the framework contract."""
    t = DBSCAN(runner=lambda *_: "@")
    assert isinstance(t, AbstractTool)
    assert t.tool_input is DBSCANInput
    assert t.tool_output is DBSCANOutput
    assert t.tool_name == "DBSCAN"


def test_encode_bipartite() -> None:
    """Genes/gene-sets get stable indices; encoding has the num*num*num*links header."""
    encoded, genes, genesets = encode_bipartite(GENE_SYMBOLS)
    assert genes == {"a": 0, "b": 1, "c": 2}
    assert genesets == {"GS1": 0, "GS2": 1}
    # 3 genes, 2 gene sets, 4 links: a-GS1, b-GS1, b-GS2, c-GS2
    assert encoded == "3*2*4*0*0*1*0*1*1*2*1*"


def test_decode_clusters_maps_indices_to_symbols() -> None:
    """JSON 2D array of gene indices decodes back to gene symbols."""
    _, genes, _ = encode_bipartite(GENE_SYMBOLS)
    assert decode_clusters(json.dumps([[0, 1], [2]]), genes) == [["a", "b"], ["c"]]


def test_decode_clusters_no_clusters_sentinel() -> None:
    """'@' (and empty) output means no clusters."""
    _, genes, _ = encode_bipartite(GENE_SYMBOLS)
    assert decode_clusters("@", genes) == []
    assert decode_clusters("", genes) == []


def test_run_skips_when_too_few_genes() -> None:
    """ran=False when num_genes - 1 < min_points (binary not invoked)."""
    called = []
    tool = DBSCAN(runner=lambda *a: called.append(a) or "@")
    out = tool.run(DBSCANInput(gene_symbols=GENE_SYMBOLS, epsilon=0.5, min_points=10))
    assert isinstance(out, DBSCANOutput)
    assert out.ran is False
    assert out.clusters == []
    assert called == []  # binary not run


def test_run_invokes_runner_and_decodes() -> None:
    """run() encodes input, calls the runner, and decodes the cluster output."""
    captured = {}

    def fake_runner(encoded: str, epsilon: float, min_points: int) -> str:
        captured["args"] = (encoded, epsilon, min_points)
        return json.dumps([[0, 1]])  # genes a, b cluster together

    out = DBSCAN(runner=fake_runner).run(
        DBSCANInput(gene_symbols=GENE_SYMBOLS, epsilon=0.5, min_points=2)
    )
    assert out.ran is True
    assert out.clusters == [["a", "b"]]
    assert out.num_genes == 3
    assert out.num_genesets == 2
    assert captured["args"] == ("3*2*4*0*0*1*0*1*1*2*1*", 0.5, 2)


def test_run_no_clusters() -> None:
    """A '@' result yields ran=True with no clusters."""
    out = DBSCAN(runner=lambda *_: "@").run(
        DBSCANInput(gene_symbols=GENE_SYMBOLS, epsilon=0.5, min_points=2)
    )
    assert out.ran is True
    assert out.clusters == []


def test_unconfigured_binary_raises() -> None:
    """Without a runner or binary path, running raises a helpful error."""
    tool = DBSCAN()  # no runner, no binary_path, env var unset in test
    with pytest.raises(RuntimeError, match="dbscan binary not configured"):
        tool.run(DBSCANInput(gene_symbols=GENE_SYMBOLS, epsilon=0.5, min_points=2))
