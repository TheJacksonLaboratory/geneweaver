"""Input/output schemas for the UpSet tool."""

from __future__ import annotations

from geneweaver.tools.framework.schema import ToolInput, ToolOutput
from pydantic import BaseModel, Field


class UpSetInput(ToolInput):
    """Input for the UpSet tool.

    ``gene_memberships`` maps each gene set id to its genes (resolved by the caller; if
    homology is desired, genes should already be homology-keyed). ``include_zeros`` emits
    every gene-set combination, even those with no genes.
    """

    geneset_ids: list[str] = Field(default_factory=list)
    gene_memberships: dict[str, list[str]] = Field(default_factory=dict)
    include_homology: bool = False
    include_zeros: bool = False


class UpSetIntersection(BaseModel):
    """Number of genes belonging to exactly this combination of gene sets."""

    genesets: list[str]
    size: int


class UpSetOutput(ToolOutput):
    """UpSet intersection sizes (genes per exact gene-set combination)."""

    geneset_ids: list[str]
    include_homology: bool
    intersections: list[UpSetIntersection]
