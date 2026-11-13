"""Schema for search API."""

from datetime import date
from typing import Annotated, Literal

from geneweaver.core.enum import GenesetTier, ScoreType, Species
from geneweaver.db.query.search.search import MAX_GENES
from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

#: Result columns the search can sort by (G3-777); see `geneweaver.db.query.search.search`.
SortKey = Literal["id", "name", "size", "species", "tier", "score_type", "created", "updated"]

#: One searched gene, by any of its identifiers.
GeneIdentifierText = Annotated[str, StringConstraints(min_length=1, max_length=100)]


class GenesetSearch(BaseModel):
    """Schema for geneset search.

    Text, genes, a gene set id, or any of them together: text matches a gene set's name and
    other metadata; genes keep the gene sets holding them (G3-764), all of them or any
    (G3-832), and by default their homologs in other species too (G3-834); an id looks one
    gene set up. Every other filter combines with them (G3-777). Results are the gene sets the caller
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
    gene: list[GeneIdentifierText] | None = Field(
        None,
        max_length=MAX_GENES,
        description=(
            f"Only gene sets holding these genes (at most {MAX_GENES}), each by any of its "
            "identifiers. Repeat the parameter for several: gene=Drd2&gene=Tp53. Each result "
            "then lists, in matched_genes, which of its genes matched."
        ),
    )
    gene_match: Literal["all", "any"] = Field(
        "all",
        description="With several genes: 'all' needs every one in a gene set, 'any' one.",
    )
    homology: bool = Field(
        True,
        description=(
            "Also match each gene's homologs in any species (TP53 finds mouse Trp53), as the "
            "analysis tools do. false matches the identifier's own genes only."
        ),
    )
    p_value: float | None = Field(
        None,
        ge=0,
        le=1,
        description="With genes: p-value gene sets where each gene's value is <= this.",
    )
    q_value: float | None = Field(
        None,
        ge=0,
        le=1,
        description="With genes: q-value gene sets where each gene's value is <= this.",
    )
    correlation_low: float | None = Field(
        None, description="With genes: correlation gene sets where each one's value is >= this."
    )
    correlation_high: float | None = Field(
        None, description="With genes: correlation gene sets where each one's value is <= this."
    )
    effect_low: float | None = Field(
        None, description="With genes: effect gene sets where each one's value is >= this."
    )
    effect_high: float | None = Field(
        None, description="With genes: effect gene sets where each one's value is <= this."
    )
    threshold_mode: Literal["only", "first"] = Field(
        "only",
        description=(
            "With genes and cutoffs: 'only' returns the gene sets whose scores for the genes "
            "pass; 'first' returns every gene set holding them, those where the most genes "
            "pass first."
        ),
    )

    @field_validator("gene", mode="after")
    @classmethod
    def _distinct_genes(cls, genes: list[str] | None) -> list[str] | None:
        """Trimmed, blanks dropped, and each gene once (ignoring case, as matching does)."""
        if genes is None:
            return None
        seen: set[str] = set()
        distinct = []
        for gene in (gene.strip() for gene in genes):
            if gene and gene.lower() not in seen:
                seen.add(gene.lower())
                distinct.append(gene)
        return distinct or None

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
