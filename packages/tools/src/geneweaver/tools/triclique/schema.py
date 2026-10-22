"""Input/output schemas for Triclique (legacy TricliqueViewer)."""

from __future__ import annotations

from geneweaver.tools.framework.schema import ToolInput, ToolOutput
from pydantic import BaseModel, Field, model_validator

#: Legacy refused more shared genes than this ("projects too large"): the search is a
#: maximal-clique enumeration, exponential in the worst case.
MAX_SHARED_GENES = 50


class TricliqueInput(ToolInput):
    """Two groups of gene sets and their genes.

    Legacy took two *projects*; v3 has none yet, so the groups are lists of gene set ids.
    ``gene_memberships`` covers every gene set in both groups, resolved by the caller (with
    homology merged and thresholds applied, if asked for).
    """

    group_a: list[str] = Field(..., min_length=1)
    group_b: list[str] = Field(..., min_length=1)
    gene_memberships: dict[str, list[str]] = Field(default_factory=dict)
    include_homology: bool = False

    @model_validator(mode="after")
    def _disjoint(self) -> TricliqueInput:
        """A gene set is in one group or the other."""
        both = sorted(set(self.group_a) & set(self.group_b))
        if both:
            raise ValueError(f"Gene sets in both groups: {', '.join(both)}.")
        return self


class Triclique(BaseModel):
    """A clique across the three parts: every gene is in every gene set of both groups."""

    group_a: list[str]
    group_b: list[str]
    genes: list[str]
    edges: int = Field(
        ..., description="Links between parts: |A|x|B| + |A|x|genes| + |B|x|genes|."
    )


class TricliqueOutput(ToolOutput):
    """The maximum triclique by links (legacy's result), and by size."""

    group_a: list[str]
    group_b: list[str]
    include_homology: bool
    shared_genes: list[str] = Field(..., description="Genes in both groups, the third part.")
    maximal_tricliques: int = Field(..., description="Maximal tricliques the search found.")
    edge_maximum: Triclique | None = Field(
        ..., description="The triclique with the most links: legacy's result."
    )
    vertex_maximum: Triclique | None = Field(
        ..., description="The triclique with the most gene sets and genes."
    )
