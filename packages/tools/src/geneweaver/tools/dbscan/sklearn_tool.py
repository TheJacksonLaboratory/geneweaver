"""In-process DBSCAN variant using C/C++-backed libraries (scipy + scikit-learn).

An alternative to the subprocess-based ``DBSCAN`` (which shells out to the TOOLBOX C++
binary). It reproduces the legacy algorithm's *structure* — DBSCAN over the gene
co-membership graph using BFS hop distance — but runs entirely in-process:

  gene co-membership graph (scipy sparse)
    -> all-pairs hop distance (scipy.sparse.csgraph.shortest_path, C-backed)
    -> sklearn.cluster.DBSCAN(metric="precomputed")

Why this exists: it avoids the binary's process-spawn + serialise-the-whole-graph-into-one
argv-string overhead (and the ARG_MAX risk), and is far more maintainable. See the module
docstring of ``tool.py`` for the binary wrapper it is compared against.

Equivalence caveat: this is a clean reimplementation, not a bit-for-bit clone. The legacy
``regionQuery`` uses an idiosyncratic BFS level count (``distance < epsilon``) and a custom
expandCluster; sklearn uses ``eps`` as ``<=`` and standard core/border handling. So exact
cluster output should be validated against the binary on real data, and ``epsilon`` may need
tuning. Shares the same DBSCANInput/DBSCANOutput as the binary tool for direct comparison.

Requires the ``sklearn`` extra: ``pip install geneweaver-tools[sklearn]``.
"""

from __future__ import annotations

from geneweaver.tools.framework.abstract import AbstractTool

from .schema import DBSCANInput, DBSCANOutput

try:
    import numpy as np
    from scipy.sparse import csr_matrix, identity
    from sklearn.cluster import DBSCAN as _SklearnDBSCAN
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "geneweaver.tools.dbscan.sklearn_tool requires the 'sklearn' extra: "
        "pip install geneweaver-tools[sklearn]"
    ) from exc


def build_gene_graph(
    gene_symbols: dict[str, list[str]],
) -> tuple[csr_matrix, dict[str, int]]:
    """Build the gene co-membership graph (genes adjacent iff they share a gene set).

    :return: (adjacency, gene_index) — a symmetric sparse 0/1 gene x gene matrix and the
        gene -> row index map.
    """
    genes: dict[str, int] = {}
    for members in gene_symbols.values():
        for member in members:
            genes.setdefault(str(member), len(genes))

    rows: list[int] = []
    cols: list[int] = []
    for members in gene_symbols.values():
        idx = [genes[str(m)] for m in members]
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                rows.extend((idx[a], idx[b]))
                cols.extend((idx[b], idx[a]))

    n = len(genes)
    data = np.ones(len(rows), dtype=np.int8)
    return csr_matrix((data, (rows, cols)), shape=(n, n)), genes


def neighbor_graph(adjacency: csr_matrix, eps_hops: int) -> csr_matrix:
    """Sparse "within eps_hops" neighbour graph (incl. self), without all-pairs distances.

    Built from bounded sparse matrix powers (A, A^2, ... A^eps_hops) instead of a dense
    n x n shortest-path matrix, so it scales with the number of *edges*, not n^2. Stored
    entries are set to distance 1.0 (the eps radius is baked into which entries exist), so
    a downstream DBSCAN with eps=1.0 treats every stored entry as a neighbour.
    """
    n = adjacency.shape[0]
    adj = (adjacency != 0).astype(np.float64)
    reach = adj.copy()
    power = adj.copy()
    for _ in range(int(eps_hops) - 1):
        power = (power @ adj != 0).astype(np.float64)
        reach = (reach + power != 0).astype(np.float64)
    reach = (reach + identity(n, format="csr") != 0).astype(np.float64)
    return reach.tocsr()


def cluster_labels(adjacency: csr_matrix, epsilon: float, min_points: int) -> np.ndarray:
    """Run DBSCAN over the sparse eps-hop neighbour graph; labels (-1 = noise)."""
    n = adjacency.shape[0]
    if n == 0:
        return np.empty(0, dtype=int)
    graph = neighbor_graph(adjacency, int(epsilon))
    # All stored entries are at distance 1.0, so eps=1.0 == "neighbours within eps hops".
    model = _SklearnDBSCAN(eps=1.0, min_samples=min_points, metric="precomputed")
    return model.fit_predict(graph)


def labels_to_clusters(labels: np.ndarray, genes: dict[str, int]) -> list[list[str]]:
    """Group gene symbols by DBSCAN label, dropping noise (-1)."""
    index_to_gene = {idx: gene for gene, idx in genes.items()}
    clusters: dict[int, list[str]] = {}
    for idx, label in enumerate(labels):
        if label == -1:
            continue
        clusters.setdefault(int(label), []).append(index_to_gene[idx])
    return [clusters[key] for key in sorted(clusters)]


class SklearnDBSCAN(AbstractTool):
    """DBSCAN over the gene co-membership graph, in-process (scipy + scikit-learn)."""

    @property
    def tool_input(self) -> type[DBSCANInput]:
        """Input schema for the tool."""
        return DBSCANInput

    @property
    def tool_output(self) -> type[DBSCANOutput]:
        """Output schema for the tool."""
        return DBSCANOutput

    def run(self, tool_input: DBSCANInput) -> DBSCANOutput:
        """Cluster the genes in-process; skip (ran=False) when too few for min_points."""
        adjacency, genes = build_gene_graph(tool_input.gene_symbols)
        num_genes = len(genes)
        num_genesets = len(tool_input.gene_symbols)

        if num_genes - 1 < int(tool_input.min_points):
            return DBSCANOutput(
                ran=False, clusters=[], num_genes=num_genes, num_genesets=num_genesets
            )

        labels = cluster_labels(adjacency, tool_input.epsilon, int(tool_input.min_points))
        return DBSCANOutput(
            ran=True,
            clusters=labels_to_clusters(labels, genes),
            num_genes=num_genes,
            num_genesets=num_genesets,
        )
