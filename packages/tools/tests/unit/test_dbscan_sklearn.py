"""Tests for the default in-process (scipy + sklearn) DBSCAN."""

import pytest

pytest.importorskip("sklearn")
pytest.importorskip("scipy")

from geneweaver.tools.dbscan import DBSCANInput, DBSCANOutput
from geneweaver.tools.dbscan.sklearn_tool import (
    DBSCAN,
    build_gene_graph,
    cluster_labels,
    labels_to_clusters,
)
from geneweaver.tools.framework.abstract import AbstractTool

# Two tight triangles (a,b,c) and (x,y,z), connected by gene-set co-membership,
# plus an isolated gene "lone".
GENE_SYMBOLS = {
    "GS1": ["a", "b", "c"],
    "GS2": ["x", "y", "z"],
    "GS3": ["lone"],
}


def test_package_default_dbscan_is_in_process() -> None:
    """`from geneweaver.tools.dbscan import DBSCAN` resolves to the in-process implementation."""
    import geneweaver.tools.dbscan as dbscan_pkg

    assert dbscan_pkg.DBSCAN is DBSCAN  # the lazy default == sklearn_tool.DBSCAN
    assert dbscan_pkg.SklearnDBSCAN is DBSCAN  # back-compat alias
    assert dbscan_pkg.DBSCAN is not dbscan_pkg.BinaryDBSCAN


def test_is_abstract_tool() -> None:
    """The in-process DBSCAN implements the framework contract and shares DBSCAN I/O."""
    t = DBSCAN()
    assert isinstance(t, AbstractTool)
    assert t.tool_input is DBSCANInput
    assert t.tool_output is DBSCANOutput
    assert t.tool_name == "DBSCAN"


def test_build_gene_graph_is_co_membership() -> None:
    """Genes are adjacent iff they share a gene set."""
    adjacency, genes = build_gene_graph(GENE_SYMBOLS)
    assert set(genes) == {"a", "b", "c", "x", "y", "z", "lone"}
    dense = adjacency.toarray()
    # a-b adjacent (share GS1); a-x not (different sets)
    assert dense[genes["a"]][genes["b"]] == 1
    assert dense[genes["a"]][genes["x"]] == 0


def test_run_finds_two_clusters() -> None:
    """With eps=1, min_points=3 the two triangles cluster; 'lone' is noise."""
    out = DBSCAN().run(DBSCANInput(gene_symbols=GENE_SYMBOLS, epsilon=1, min_points=3))
    assert isinstance(out, DBSCANOutput)
    assert out.ran is True
    clusters = {frozenset(c) for c in out.clusters}
    assert frozenset({"a", "b", "c"}) in clusters
    assert frozenset({"x", "y", "z"}) in clusters
    # the isolated gene is not in any cluster
    assert all("lone" not in c for c in out.clusters)


def test_run_skips_when_too_few_genes() -> None:
    """ran=False when num_genes - 1 < min_points."""
    out = DBSCAN().run(DBSCANInput(gene_symbols={"GS1": ["a", "b"]}, epsilon=1, min_points=10))
    assert out.ran is False
    assert out.clusters == []


def test_labels_to_clusters_drops_noise() -> None:
    """Noise label (-1) is excluded; clusters are grouped by label."""
    _, genes = build_gene_graph(GENE_SYMBOLS)
    labels = cluster_labels(build_gene_graph(GENE_SYMBOLS)[0], epsilon=1, min_points=3)
    clusters = labels_to_clusters(labels, genes)
    assert all("lone" not in c for c in clusters)
    assert len(clusters) == 2
