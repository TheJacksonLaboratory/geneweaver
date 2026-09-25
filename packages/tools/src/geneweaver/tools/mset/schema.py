"""Input/output schemas for the MSET tool."""

from __future__ import annotations

from geneweaver.tools.framework.schema import ToolInput, ToolOutput
from pydantic import Field


class MSETInput(ToolInput):
    """Input for MSET (Modular Single-set Enrichment Test).

    Compares two gene lists against their background gene universes via the MSET C++ binary
    (a Monte-Carlo sampling test).

    Each background is the **resolved gene universe** for its list, supplied by the caller as
    a list of gene identifiers. MSET reads no background files and touches no database: the
    caller owns resolving the universe, exactly as it already owns the two gene lists.

    Legacy instead named one of ~301 precomputed ``*BG.txt`` files in a background directory.
    Those files were a denormalised cache of database state and went stale on every gene
    reload (GWC-45 / G3-766), and they defined the universe as only those genes appearing in
    *curated* gene sets, so a gene unique to a Tier-IV set was outside its own universe even
    when the file was fresh (GWC-51 / G3-783). Resolving at run time removes both, along with
    the regeneration job and the per-environment storage. See G3-784.
    """

    group_1_genes: list[str] = Field(default_factory=list)
    group_2_genes: list[str] = Field(default_factory=list)
    group_1_background: list[str]
    group_2_background: list[str]
    number_of_samples: int = 1000
    over_representation: bool = True


class MSETOutput(ToolOutput):
    """MSET result: the binary's summary + histogram, plus the gene-list intersection."""

    intersect_genes: list[str]
    mset_data: dict[str, str] = Field(default_factory=dict)
    mset_hist: dict[str, str] = Field(default_factory=dict)
