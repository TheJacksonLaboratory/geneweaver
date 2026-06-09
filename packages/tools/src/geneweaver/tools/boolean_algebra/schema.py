"""Input/output schemas for the Boolean Algebra tool."""

from __future__ import annotations

from typing import Any

from geneweaver.tools.framework.schema import ToolInput, ToolOutput
from pydantic import Field

# A homolog row as produced by the legacy GET_HOMOLOGS_SQL query:
# (hom_source_id, ode_gene_id, ode_ref_id, sp_id, gs_id, gs_abbreviation)
HomologRow = list[Any]


class BooleanAlgebraInput(ToolInput):
    """Input for the Boolean Algebra tool.

    DB access (resolving the homolog rows and species for the gene sets) is the
    caller's responsibility; the resolved data is passed in here so the tool itself
    stays pure. ``homolog_data`` rows are
    ``[hom_source_id, ode_gene_id, ode_ref_id, sp_id, gs_id, gs_abbreviation]``.
    """

    relation: str  # "union" | "intersection" | "except" (case-insensitive)
    at_least: int = 2
    geneset_ids: list[int]
    species_ids: list[int]
    homolog_data: list[HomologRow] = Field(default_factory=list)


class BooleanAlgebraOutput(ToolOutput):
    """Algorithmic result of a Boolean Algebra run.

    Presentation-only fields from the legacy tool (color/tooltip/border styling) are
    intentionally omitted — those belong to the UI layer, not the tool.
    """

    relation: str
    at_least: int
    num_genesets: int
    num_species: int
    geneset_ids: list[int]
    species_ids: list[int]
    # group key -> list of [ode_gene_id, ode_ref_id, sp_id, gs_id]
    bool_results: dict[int, list[list[Any]]]
    # only present when 1..10 result gene sets
    circle_groups: dict[int, list[Any]] | None = None
    # intersection size -> {group key -> rows}; present for intersection/except
    intersect_results: dict[int, dict[int, list[list[Any]]]] | None = None
    # present only for the "except" relation
    bool_except: dict[int, dict[int, list[list[Any]]]] | None = None
    # sp_id -> {"unique": [...], "intersection": [...], "species": [...]}
    bool_cluster: dict[int, dict[str, list[Any]]]
