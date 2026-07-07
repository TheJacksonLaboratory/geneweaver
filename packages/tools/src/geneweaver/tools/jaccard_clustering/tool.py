"""Jaccard Clustering tool, reimplemented on the AbstractTool framework.

Ported from the legacy Celery worker ``legacy/tools-worker/tools/JaccardClustering.py``,
which hand-rolled agglomerative clustering (ward/complete/average/mcquitty/single) over a
Jaccard distance matrix of gene sets and built a dendrogram tree.

Improvement: use ``scipy.cluster.hierarchy`` (correct, C-backed, O(n^2 log n)) instead of
the legacy custom O(n^3) Python clustering. Same methods (mcquitty -> scipy "weighted").
The presentation outputs (PNG/PDF dendrogram images) are dropped; this returns the tree.

Requires the ``sklearn`` extra (it provides scipy): ``pip install geneweaver-tools[sklearn]``.
"""

from __future__ import annotations

from geneweaver.tools.framework.abstract import AbstractTool

from .schema import (
    ClusterNode,
    JaccardClusteringInput,
    JaccardClusteringOutput,
)

try:
    import numpy as np
    from scipy.cluster.hierarchy import linkage, to_tree
    from scipy.spatial.distance import squareform
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "geneweaver.tools.jaccard_clustering requires the 'sklearn' extra (for scipy): "
        "pip install geneweaver-tools[sklearn]"
    ) from exc

# Map the legacy method names to scipy's.
_METHOD_MAP = {
    "ward": "ward",
    "complete": "complete",
    "average": "average",
    "mcquitty": "weighted",
    "single": "single",
}


def _to_cluster_node(node: object, geneset_ids: list[str]) -> ClusterNode:
    """Convert a scipy ClusterNode tree into the serialisable ClusterNode schema."""
    if node.is_leaf():
        return ClusterNode(geneset_id=geneset_ids[node.id])
    return ClusterNode(
        distance=float(node.dist),
        children=[
            _to_cluster_node(node.get_left(), geneset_ids),
            _to_cluster_node(node.get_right(), geneset_ids),
        ],
    )


def cluster_tree(
    similarity: list[list[float]], method: str, geneset_ids: list[str]
) -> ClusterNode | None:
    """Build a dendrogram from a Jaccard similarity matrix; None for < 2 gene sets."""
    n = len(similarity)
    if n < 2:
        return None
    sim = np.asarray(similarity, dtype=float)
    # Distance = 1 - similarity; force a clean zero diagonal and symmetry for squareform.
    distance = 1.0 - sim
    np.fill_diagonal(distance, 0.0)
    distance = (distance + distance.T) / 2.0
    condensed = squareform(distance, checks=False)
    linkage_matrix = linkage(condensed, method=_METHOD_MAP[method])
    return _to_cluster_node(to_tree(linkage_matrix), geneset_ids)


class JaccardClustering(AbstractTool):
    """Hierarchical clustering of gene sets by Jaccard distance."""

    @property
    def tool_input(self) -> type[JaccardClusteringInput]:
        """Input schema for the tool."""
        return JaccardClusteringInput

    @property
    def tool_output(self) -> type[JaccardClusteringOutput]:
        """Output schema for the tool."""
        return JaccardClusteringOutput

    def run(self, tool_input: JaccardClusteringInput) -> JaccardClusteringOutput:
        """Cluster the gene sets into a dendrogram using the requested linkage method."""
        tree = cluster_tree(tool_input.similarity, tool_input.method, tool_input.geneset_ids)
        return JaccardClusteringOutput(
            geneset_ids=tool_input.geneset_ids,
            method=tool_input.method,
            tree=tree,
        )
