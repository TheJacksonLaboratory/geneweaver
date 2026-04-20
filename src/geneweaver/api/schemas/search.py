"""Schema for search API."""

from datetime import date

from geneweaver.core.enum import GenesetTier, ScoreType, Species
from pydantic import BaseModel, Field


class GenesetSearch(BaseModel):
    """Schema for geneset search."""

    search_text: str
    publication_id: int | None = None
    pubmed_id: int | None = None
    species: set[Species] | None = None
    curation_tier: set[GenesetTier] | None = None
    score_type: set[ScoreType] | None = None
    lte_count: int | None = None
    gte_count: int | None = None
    created_before: date | None = None
    created_after: date | None = None
    updated_before: date | None = None
    updated_after: date | None = None
    limit: int | None = Field(25, ge=0, le=1000)
    offset: int | None = None
