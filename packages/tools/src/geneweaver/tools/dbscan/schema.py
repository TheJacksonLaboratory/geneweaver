"""Input/output schemas for the DBSCAN tool."""

from __future__ import annotations

from geneweaver.tools.framework.schema import ToolInput, ToolOutput
from pydantic import Field


class DBSCANInput(ToolInput):
    """Input for the DBSCAN tool.

    ``gene_symbols`` maps each gene set id to its list of gene symbols/ids (resolved by
    the caller); DBSCAN clusters the genes by their gene-set co-membership.
    """

    gene_symbols: dict[str, list[str]] = Field(default_factory=dict)
    # Integer neighbourhood radius (BFS hop count). The dbscan binary parses epsilon with an
    # integer ``atol`` (rejecting any non-digit, e.g. "1.0"), so this is an int, not a float.
    epsilon: int
    min_points: int
    geneset_ids: list[str] = Field(default_factory=list)


class DBSCANOutput(ToolOutput):
    """DBSCAN clustering result.

    ``ran`` is False when there are too few genes to satisfy ``min_points`` (the legacy
    ``ran`` flag). ``clusters`` is a list of clusters, each a list of gene symbols.
    """

    ran: bool
    clusters: list[list[str]] = Field(default_factory=list)
    num_genes: int
    num_genesets: int
    # Gene -> the input gene sets containing it, for every clustered gene: the co-membership
    # the clusters were built from, which legacy's "Wires" view drew as a gene network.
    gene_genesets: dict[str, list[str]] = Field(default_factory=dict)


def clustered_gene_genesets(
    clusters: list[list[str]], gene_symbols: dict[str, list[str]]
) -> dict[str, list[str]]:
    """Map each clustered gene to the gene sets (in input order) that contain it."""
    clustered = {gene for cluster in clusters for gene in cluster}
    memberships: dict[str, list[str]] = {gene: [] for gene in clustered}
    for geneset_id, members in gene_symbols.items():
        for gene in dict.fromkeys(members):
            if gene in memberships:
                memberships[gene].append(geneset_id)
    return memberships
