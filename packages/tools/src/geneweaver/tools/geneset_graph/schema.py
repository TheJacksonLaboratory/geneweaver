"""Input/output schemas for GeneSet Graph (legacy GeneSetViewer)."""

from __future__ import annotations

from typing import Literal

from geneweaver.tools.framework.schema import ToolInput, ToolOutput
from pydantic import BaseModel, Field, field_validator


class GenesetGraphInput(ToolInput):
    """What the graph is drawn from.

    ``gene_memberships`` maps each gene set id to its genes, resolved by the caller (with
    homology merged and thresholds applied, if asked for). ``min_degree`` is legacy's
    "Minimum Degree (connectedness) of displayed genes": a gene is drawn only if at least
    that many of the gene sets hold it; ``"auto"`` picks it as legacy did.
    """

    geneset_ids: list[str] = Field(default_factory=list)
    gene_memberships: dict[str, list[str]] = Field(default_factory=dict)
    include_homology: bool = False
    min_degree: int | Literal["auto"] = Field(default=1)
    suppress_disconnected: bool = Field(
        default=True,
        description="Leave out gene sets none of whose genes reach the minimum degree.",
    )
    emphasis_genes: list[str] = Field(
        default_factory=list, description="Genes to highlight, matched case-insensitively."
    )

    @field_validator("min_degree")
    @classmethod
    def _at_least_one(cls, value: int | str) -> int | str:
        """Refuse a minimum degree below 1; legacy's floor."""
        if isinstance(value, int) and value < 1:
            raise ValueError("min_degree must be at least 1, or 'auto'.")
        return value


class GenesetGraphSet(BaseModel):
    """A gene set node."""

    id: str
    genes: int = Field(..., description="Genes of this set drawn in the graph.")
    size: int = Field(..., description="Genes the set holds in this run.")


class GenesetGraphGene(BaseModel):
    """A gene node: its degree is how many of the run's gene sets hold it."""

    symbol: str
    degree: int
    genesets: list[str]
    emphasized: bool = False


class GenesetGraphOutput(ToolOutput):
    """The graph: gene sets, the genes drawn, and legacy's degree statistics."""

    geneset_ids: list[str]
    include_homology: bool
    min_degree: int = Field(..., description="The minimum degree applied ('auto' resolved).")
    genesets: list[GenesetGraphSet]
    genes: list[GenesetGraphGene] = Field(..., description="Drawn genes, highest degree first.")
    total_genes: int = Field(..., description="Genes across all gene sets, drawn or not.")
    min_gene_degree: int
    max_gene_degree: int
    avg_gene_degree: float
