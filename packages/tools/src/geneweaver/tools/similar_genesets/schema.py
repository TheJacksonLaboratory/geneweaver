"""Input and output schemas for Similar gene sets.

Pure pydantic, like every tool's schema: the API validates a request against
`SimilarGenesetsInput` before submitting it, and the worker validates it again.
"""

from geneweaver.tools.thresholds import ThresholdOptions
from pydantic import BaseModel, Field

#: Legacy listed the top 500 by Jaccard (``get_similar_genesets``).
DEFAULT_LIMIT = 500


class SimilarGenesetsInput(ThresholdOptions):
    """The gene set to compare, how many to return, and the run's thresholds.

    The caller's identity is not here. It travels beside the input, signed, as ABBA's does
    (`geneweaver.tools.abba.identity`), so a run submitted to AsyncTask directly cannot
    claim someone else's private gene sets.
    """

    geneset_id: int = Field(..., ge=1, description="The gene set to find others like.")
    limit: int = Field(
        default=DEFAULT_LIMIT, ge=1, le=1000, description="The most similar gene sets to return."
    )


class SimilarGeneset(BaseModel):
    """One gene set like the viewed one, with what legacy's list and charts show."""

    gs_id: int
    name: str
    abbreviation: str | None
    species_id: int
    tier: int | None = Field(
        ...,
        description=(
            "Curation tier, 1 (Tier I) to 5 (Tier V); null for a gene set never assigned one "
            "(`cur_id` is nullable: 7,214 live gene sets on dev)."
        ),
    )
    attribution: str | None
    genes: int = Field(..., description="Its genes under the threshold choice, homologs as one.")
    shared: int = Field(..., description="Genes it shares with the viewed gene set.")
    jaccard: float = Field(..., description="shared / (viewed genes + genes - shared).")


class SimilarGenesetsOutput(BaseModel):
    """The most similar gene sets, most similar first."""

    geneset_id: int
    genes: int = Field(..., description="The viewed gene set's genes, homologs as one.")
    thresholds: dict = Field(..., description="The threshold choice the run used.")
    compared: int = Field(..., description="Gene sets sharing at least one gene with it.")
    genesets: list[SimilarGeneset]
    species: dict[int, str] = Field(..., description="Species names, for the charts.")
    tiers: dict[int, str] = Field(..., description="Curation tier names, for the charts.")
