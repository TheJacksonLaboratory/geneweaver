"""Request and response schemas for running analysis tools."""

from pydantic import BaseModel, Field, field_validator, model_validator

#: With `include_zeros` the tool emits every combination of the requested gene sets --
#: 2^n - 1 of them -- rather than only those with genes. At the 20-set ceiling that is
#: over a million rows to build and serialise, which a synchronous request has no business
#: doing, so this case needs a much tighter bound than the sparse one.
MAX_GENESETS_WITH_ZEROS = 10


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
            f"2^n - 1, so this is capped at {MAX_GENESETS_WITH_ZEROS} gene sets."
        ),
    )
    include_homology: bool = Field(
        default=False,
        description=(
            "Merge homologous genes across the gene sets, so sets from different species "
            'intersect on their orthologs (legacy\'s "Homology: Included").'
        ),
    )

    @field_validator("geneset_ids")
    @classmethod
    def _reject_duplicate_ids(cls, value: list[int]) -> list[int]:
        """Refuse repeated ids rather than silently collapsing them.

        Gene memberships resolve into a dict keyed by gene set id, so a repeated id
        becomes one entry while the request still claims two. The result would then
        describe fewer gene sets than were asked for, with no indication why.
        """
        duplicates = sorted({item for item in value if value.count(item) > 1})
        if duplicates:
            raise ValueError(
                "Duplicate gene set ids: " + ", ".join(str(item) for item in duplicates)
            )
        return value

    @model_validator(mode="after")
    def _bound_zero_combinations(self) -> "UpSetRequest":
        """Keep a synchronous run's output bounded when every combination is requested."""
        if self.include_zeros and len(self.geneset_ids) > MAX_GENESETS_WITH_ZEROS:
            raise ValueError(
                f"include_zeros is limited to {MAX_GENESETS_WITH_ZEROS} gene sets "
                f"({len(self.geneset_ids)} requested): it emits every combination, "
                f"2^n - 1, which is "
                f"{2 ** len(self.geneset_ids) - 1:,} for this request."
            )
        return self


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


class ToolRunRequest(BaseModel):
    """Parameters for running any registered tool.

    The same bounds as `UpSetRequest` on the gene-set list, because the reason for them is
    the same: a synchronous request. `parameters` is deliberately free-form -- each tool
    reads its own options (`epsilon`/`min_points` for DBSCAN, `relation` for
    BooleanAlgebra, `method` for JaccardClustering) and documents them in its input
    builder. Typing it per tool would mean a request model per tool for no gain while runs
    are synchronous; when execution moves to AsyncTask the parameters become
    `odestatic.tool_param` rows and get validated from the database (roadmap A5).
    """

    geneset_ids: list[int] = Field(
        ...,
        min_length=2,
        max_length=20,
        description="Gene sets to analyse. Capped to keep a synchronous run bounded.",
    )
    parameters: dict = Field(
        default_factory=dict,
        description=(
            "Tool-specific options; unknown keys are ignored. `include_homology` "
            "(upset, dbscan, hypergeometric, jaccard_clustering, jaccard_similarity, "
            "phenome_map, combine); `pairwise_deletion` (jaccard_similarity, "
            "hypergeometric); `p_value_threshold` (jaccard_similarity, phenome_map); "
            "`method` (jaccard_clustering: ward, single, centroid, mcquitty, average, "
            "complete); `relation` and `at_least` (boolean_algebra); `epsilon` and "
            "`min_points` (dbscan); `number_of_samples` (mset); `min_genes`, "
            "`max_level`, `use_fdr`, `disable_bootstrap` (phenome_map)."
        ),
    )

    @field_validator("geneset_ids")
    @classmethod
    def _reject_duplicate_ids(cls, value: list[int]) -> list[int]:
        """Refuse repeated ids rather than silently collapsing them."""
        duplicates = sorted({item for item in value if value.count(item) > 1})
        if duplicates:
            raise ValueError(
                "Duplicate gene set ids: " + ", ".join(str(item) for item in duplicates)
            )
        return value


class ToolAvailability(BaseModel):
    """Whether one tool can be run through this API, and anything qualifying its result."""

    available: bool = Field(..., description="Whether a run would be accepted.")
    reason: str | None = Field(default=None, description="Why it cannot run, when it cannot.")
    caveat: str | None = Field(
        default=None,
        description="Qualifies how a successful result should be read, if anything does.",
    )


class ToolRunResult(BaseModel):
    """The result of running any tool.

    `result` is the tool's own output, dumped as given. Shaping it per tool in the API
    would mean nine response models that add nothing: the tools already define their output
    schemas, and the UI renders per tool regardless.
    """

    tool: str = Field(..., description="The tool that produced this result.")
    geneset_ids: list[int] = Field(..., description="The gene sets that were run.")
    gene_counts: dict[str, int] = Field(
        ..., description="Genes resolved per gene set, keyed by gene set id."
    )
    caveat: str | None = Field(
        default=None, description="Qualifies how to read this result, if anything does."
    )
    result: dict = Field(..., description="The tool's own output.")
