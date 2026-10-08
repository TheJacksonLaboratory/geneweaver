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
    # Gene -> the input gene sets containing it, for every input gene on a run that ran: the
    # co-membership the clusters were built from, which legacy's "Wires" view drew as a gene
    # network. Noise genes are included -- legacy drew them grey -- so `clusters` decides only
    # the colour, not whether a gene is drawn.
    gene_genesets: dict[str, list[str]] = Field(default_factory=dict)


def gene_genesets(gene_symbols: dict[str, list[str]]) -> dict[str, list[str]]:
    """Map every input gene to the gene sets (in input order) that contain it."""
    memberships: dict[str, list[str]] = {}
    for geneset_id, members in gene_symbols.items():
        for gene in dict.fromkeys(members):
            memberships.setdefault(gene, []).append(geneset_id)
    return memberships
