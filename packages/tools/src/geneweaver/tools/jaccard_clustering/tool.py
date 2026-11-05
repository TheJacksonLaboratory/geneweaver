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
    from scipy.cluster.hierarchy import linkage
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
    "centroid": "centroid",
}


def _tree_from_linkage(linkage_matrix: object, geneset_ids: list[str]) -> ClusterNode:
    """Build the dendrogram from a SciPy linkage matrix.

    Does the job of ``scipy.cluster.hierarchy.to_tree``, deliberately without calling it.
    `to_tree` validates its input through SciPy's array-API compatibility layer, which
    probes for Google's JAX by doing ``getattr(sys.modules["jax"], "Array")``. In this
    project ``jax`` is a namespace package belonging to *Jackson Laboratory's*
    ``jax-apiutils``, so that attribute does not exist and SciPy raises
    ``AttributeError: module 'jax' has no attribute 'Array'`` -- which means this tool
    fails for any caller that has imported ``jax.apiutils``, as the GeneWeaver API always
    has. Nothing about the clustering needs that code path.

    The linkage matrix format is stable and documented: row ``i`` merges the clusters named
    by ``Z[i, 0]`` and ``Z[i, 1]`` at distance ``Z[i, 2]``, forming cluster ``n + i``. An
    index below ``n`` is an original gene set; at or above ``n`` it is the cluster formed by
    row ``index - n``. Left/right follow columns 0 and 1, matching `to_tree`.

    Built iteratively rather than recursively: rows are ordered so every cluster exists
    before it is referenced, and a deep dendrogram would otherwise risk the recursion limit.
    """
    leaf_count = len(geneset_ids)
    nodes: dict[int, ClusterNode] = {
        index: ClusterNode(geneset_id=geneset_id) for index, geneset_id in enumerate(geneset_ids)
    }
    for row_index, row in enumerate(linkage_matrix):
        left, right, distance = int(row[0]), int(row[1]), float(row[2])
        nodes[leaf_count + row_index] = ClusterNode(
            distance=distance, children=[nodes[left], nodes[right]]
        )
    # The last merge is the root: it is the only cluster nothing else contains.
    return nodes[leaf_count + len(linkage_matrix) - 1]


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
    return _tree_from_linkage(linkage_matrix, geneset_ids)


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
