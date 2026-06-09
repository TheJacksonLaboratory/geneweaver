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
    epsilon: float
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
