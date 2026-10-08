"""Input and output schemas for ABBA, legacy's gene-centred search.

Pure pydantic, like every tool's schema: the API validates a request against `ABBAInput`
before submitting it, and the worker validates it again before searching.
"""

from pydantic import BaseModel, Field, field_validator

#: Curation tiers (`odestatic.curation_levels.cur_id`), Tier I through Tier V.
ABBA_TIERS = (1, 2, 3, 4, 5)


class ABBAInput(BaseModel):
    """What the search runs on: seed genes and legacy's options.

    The seed is gene symbols only. Gene sets named as seeds are expanded to their genes by
    the API, which has checked the caller may read them; the worker is never handed a gene
    set id to read on someone's behalf.

    The caller's identity is not here either. It travels beside the input, signed
    (`abba.identity`), so a run submitted to AsyncTask directly cannot claim to be someone
    else and see their private gene sets.
    """

    genes: list[str] = Field(
        default_factory=list, description="Seed gene symbols, matched case-insensitively."
    )
    include_homology: bool = Field(
        default=True,
        description="Expand the seed to its homologs in the searched species (legacy default).",
    )
    min_genes: int | None = Field(
        default=None,
        ge=1,
        description="Seed genes a gene set must contain to count; null is legacy's Auto.",
    )
    min_genesets: int | None = Field(
        default=None,
        ge=1,
        description="Matching gene sets a result gene must occur in; null is legacy's Auto.",
    )
    tiers: list[int] = Field(
        default_factory=lambda: [1, 2, 3],
        min_length=1,
        description="Curation tiers to search, 1 (Tier I) to 5 (Tier V).",
    )
    species_ids: list[int] | None = Field(
        default=None,
        min_length=1,
        description="Species to restrict the search to; null searches every species.",
    )

    @field_validator("genes")
    @classmethod
    def _clean_genes(cls, value: list[str]) -> list[str]:
        """Drop blanks and repeats, keeping the caller's order."""
        genes, seen = [], set()
        for gene in (item.strip() for item in value):
            if gene and gene.lower() not in seen:
                seen.add(gene.lower())
                genes.append(gene)
        return genes

    @field_validator("tiers")
    @classmethod
    def _known_tiers(cls, value: list[int]) -> list[int]:
        """Refuse a tier that does not exist rather than silently matching nothing."""
        unknown = sorted(set(value) - set(ABBA_TIERS))
        if unknown:
            raise ValueError(f"Unknown curation tier(s) {unknown}; tiers are 1 to 5.")
        return sorted(set(value))


class ABBASeedGene(BaseModel):
    """A gene the search started from, after homology expansion."""

    ode_gene_id: int
    symbol: str
    species_id: int | None
    species: str


class ABBAGeneset(BaseModel):
    """A gene set containing seed genes."""

    gs_id: int
    name: str
    abbreviation: str | None
    description: str | None
    matches: int = Field(..., description="Seed genes this gene set contains.")
    tier: int | None
    species_id: int | None
    attribution: str | None = Field(..., description="Source, e.g. GO or MESH, if any.")
    gene_count: int | None


class ABBAGene(BaseModel):
    """A gene recurring across the matching gene sets."""

    ode_gene_id: int
    symbol: str = Field(..., description="The preferred gene symbol.")
    symbols: list[str] = Field(..., description="Every gene symbol recorded for the gene.")
    species_id: int
    species: str
    occurrences: int = Field(..., description="Matching gene sets the gene occurs in.")
    tier_counts: dict[int, int] = Field(..., description="All its gene sets, per tier.")
    species_counts: dict[int, int] = Field(
        ..., description="Gene sets of its homology group, per species."
    )


class ABBAOutput(BaseModel):
    """The result of an ABBA search: legacy's four result panels, as data."""

    tool: str = "abba"
    parameters: dict = Field(..., description="The options the search ran with.")
    available_genes: int
    available_genesets: int
    input_species: list[str]
    seed_genes: list[ABBASeedGene]
    genesets: list[ABBAGeneset] = Field(..., description="Top gene sets by matches.")
    genes: list[ABBAGene] = Field(..., description="Top genes by occurrences.")
    max_occurrences: int
    species: dict[int, str] = Field(..., description="Species names by id.")
    tiers: dict[int, str] = Field(..., description="Curation tier names by id.")
