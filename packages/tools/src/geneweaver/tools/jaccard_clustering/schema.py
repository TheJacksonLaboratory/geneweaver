"""Input/output schemas for the Jaccard Clustering tool."""

from __future__ import annotations

from typing import Literal

from geneweaver.tools.framework.schema import ToolInput, ToolOutput
from pydantic import BaseModel, Field

# Linkage methods supported by the legacy tool (mcquitty == scipy's "weighted").
LinkageMethod = Literal["ward", "complete", "average", "mcquitty", "single"]


class JaccardClusteringInput(ToolInput):
    """Input for the Jaccard Clustering tool.

    ``similarity`` is the symmetric pairwise Jaccard *similarity* matrix between the gene
    sets (n x n, diagonal 1.0), resolved by the caller from gene-set memberships. The tool
    clusters on the corresponding distance (1 - similarity).
    """

    geneset_ids: list[str] = Field(default_factory=list)
    method: LinkageMethod = "average"
    similarity: list[list[float]] = Field(default_factory=list)


class ClusterNode(BaseModel):
    """A node in the dendrogram. Leaves carry a gene set; internal nodes carry children."""

    geneset_id: str | None = None
    distance: float | None = None
    children: list[ClusterNode] = Field(default_factory=list)


class JaccardClusteringOutput(ToolOutput):
    """Hierarchical clustering result (a dendrogram of the gene sets)."""

    geneset_ids: list[str]
    method: str
    tree: ClusterNode | None  # None when there are fewer than 2 gene sets


ClusterNode.model_rebuild()
