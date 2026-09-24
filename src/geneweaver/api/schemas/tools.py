"""Request and response schemas for running analysis tools."""

from pydantic import BaseModel, Field


class UpSetRequest(BaseModel):
    """Parameters for an UpSet run.

    Mirrors `geneweaver.tools.upset.UpSetInput`, minus the resolved gene memberships --
    those come from the database, keyed by the gene set ids given here.
    """

    geneset_ids: list[int] = Field(
        ...,
        min_length=2,
        max_length=20,
        description=(
            "Gene sets to intersect. At least two, since an UpSet plot of one set is "
            "just that set; capped to keep a synchronous run bounded."
        ),
    )
    include_zeros: bool = Field(
        default=False,
        description=(
            "Include combinations with no genes. The number of combinations is "
            "2^n - 1, so this grows quickly with the number of gene sets."
        ),
    )


class UpSetIntersection(BaseModel):
    """One combination of gene sets and the number of genes exclusive to it."""

    geneset_ids: list[str] = Field(..., description="The gene sets in this combination.")
    size: int = Field(..., description="Genes appearing in exactly these gene sets.")


class UpSetResult(BaseModel):
    """The result of an UpSet run."""

    tool: str = Field(default="UpSet", description="The tool that produced this result.")
    geneset_ids: list[int] = Field(..., description="The gene sets that were run.")
    gene_counts: dict[str, int] = Field(
        ..., description="Genes resolved per gene set, keyed by gene set id."
    )
    intersections: list[UpSetIntersection] = Field(
        ..., description="Exclusive intersection sizes, largest first."
    )
