"""Tests for the Jaccard Clustering tool (scipy-backed hierarchical clustering)."""

import pytest

pytest.importorskip("scipy")

from geneweaver.tools.framework.abstract import AbstractTool
from geneweaver.tools.jaccard_clustering import (
    ClusterNode,
    JaccardClustering,
    JaccardClusteringInput,
    JaccardClusteringOutput,
)

# 4 gene sets: {0,1} very similar, {2,3} very similar, the two pairs dissimilar.
GS = ["GS0", "GS1", "GS2", "GS3"]
SIM = [
    [1.0, 0.9, 0.1, 0.1],
    [0.9, 1.0, 0.1, 0.1],
    [0.1, 0.1, 1.0, 0.9],
    [0.1, 0.1, 0.9, 1.0],
]


def _leaves(node: ClusterNode) -> set[str]:
    if node.geneset_id is not None:
        return {node.geneset_id}
    return set().union(*(_leaves(c) for c in node.children))


def test_is_abstract_tool() -> None:
    """JaccardClustering implements the framework contract."""
    t = JaccardClustering()
    assert isinstance(t, AbstractTool)
    assert t.tool_input is JaccardClusteringInput
    assert t.tool_output is JaccardClusteringOutput
    assert t.tool_name == "JaccardClustering"


def test_run_builds_dendrogram() -> None:
    """The dendrogram groups the two similar pairs before merging them."""
    out = JaccardClustering().run(
        JaccardClusteringInput(geneset_ids=GS, method="average", similarity=SIM)
    )
    assert isinstance(out, JaccardClusteringOutput)
    root = out.tree
    assert root is not None
    # root has two children, each a tight pair
    child_leaves = sorted((_leaves(c) for c in root.children), key=lambda s: sorted(s))
    assert {"GS0", "GS1"} in child_leaves
    assert {"GS2", "GS3"} in child_leaves
    # all four gene sets present as leaves
    assert _leaves(root) == set(GS)


@pytest.mark.parametrize("method", ["ward", "complete", "average", "mcquitty", "single"])
def test_all_methods_supported(method: str) -> None:
    """Every legacy linkage method maps to a valid scipy method."""
    out = JaccardClustering().run(
        JaccardClusteringInput(geneset_ids=GS, method=method, similarity=SIM)
    )
    assert out.tree is not None
    assert _leaves(out.tree) == set(GS)


def test_fewer_than_two_genesets_returns_no_tree() -> None:
    """A single gene set cannot be clustered."""
    out = JaccardClustering().run(
        JaccardClusteringInput(geneset_ids=["GS0"], method="average", similarity=[[1.0]])
    )
    assert out.tree is None
