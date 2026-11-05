"""Schema for search API."""

from datetime import date
from typing import Literal

from geneweaver.core.enum import GenesetTier, ScoreType, Species
from pydantic import BaseModel, Field, model_validator

#: Result columns the search can sort by (G3-777); see `geneweaver.db.query.search.search`.
SortKey = Literal["id", "name", "size", "species", "tier", "score_type", "created", "updated"]


class GenesetSearch(BaseModel):
    """Schema for geneset search.

    Text, a gene, a gene set id, or any of them together: text matches a gene set's name and
    other metadata; a gene keeps the gene sets holding it (G3-764); an id looks one gene set
    up. Every other filter combines with them (G3-777). Results are the gene sets the caller
    may read (``geneset_is_readable2``): admins and curators see private gene sets too.
    """

    search_text: str | None = None
    gs_id: int | None = Field(
        None, ge=1, description="Only this gene set, if the caller may read it."
    )
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
    sort_by: SortKey | None = Field(
        None, description="Sort the results by this column; unsorted when omitted."
    )
    sort_order: Literal["asc", "desc"] = "asc"
    gene: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Only gene sets holding this gene, by any of its identifiers.",
    )
    p_value: float | None = Field(
        None, ge=0, le=1, description="With gene: p-value gene sets where its value is <= this."
    )
    q_value: float | None = Field(
        None, ge=0, le=1, description="With gene: q-value gene sets where its value is <= this."
    )
    correlation_low: float | None = Field(
        None, description="With gene: correlation gene sets where its value is >= this."
    )
    correlation_high: float | None = Field(
        None, description="With gene: correlation gene sets where its value is <= this."
    )
    effect_low: float | None = Field(
        None, description="With gene: effect gene sets where its value is >= this."
    )
    effect_high: float | None = Field(
        None, description="With gene: effect gene sets where its value is <= this."
    )
    threshold_mode: Literal["only", "first"] = Field(
        "only",
        description=(
            "With gene and cutoffs: 'only' returns the gene sets whose score for the gene "
            "passes; 'first' returns every gene set holding it, those that pass first."
        ),
    )

    @model_validator(mode="after")
    def _check_search(self) -> "GenesetSearch":
        """Refuse a search with nothing to search for, or cutoffs with no gene to apply to."""
        if (
            not (self.search_text and self.search_text.strip())
            and not self.gene
            and not self.gs_id
        ):
            raise ValueError("Give search_text, a gene, or a gs_id.")
        cutoffs = (
            self.p_value,
            self.q_value,
            self.correlation_low,
            self.correlation_high,
            self.effect_low,
            self.effect_high,
        )
        if self.gene is None and any(value is not None for value in cutoffs):
            raise ValueError("Score cutoffs apply to a gene's score in each gene set: give gene.")
        for name, low, high in (
            ("correlation", self.correlation_low, self.correlation_high),
            ("effect", self.effect_low, self.effect_high),
        ):
            if low is not None and high is not None and low > high:
                raise ValueError(f"{name}_low ({low}) is above {name}_high ({high}).")
        return self
