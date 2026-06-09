"""Input/output schemas for the MSET tool."""

from __future__ import annotations

from geneweaver.tools.framework.schema import ToolInput, ToolOutput
from pydantic import Field


class MSETInput(ToolInput):
    """Input for MSET (Modular Single-set Enrichment Test).

    Compares two gene lists against their background gene universes via the MSET C++ binary
    (a Monte-Carlo sampling test). Background universes are named files in the tool's
    background directory.
    """

    group_1_genes: list[str] = Field(default_factory=list)
    group_2_genes: list[str] = Field(default_factory=list)
    group_1_background: str
    group_2_background: str
    number_of_samples: int = 1000
    over_representation: bool = True


class MSETOutput(ToolOutput):
    """MSET result: the binary's summary + histogram, plus the gene-list intersection."""

    intersect_genes: list[str]
    mset_data: dict[str, str] = Field(default_factory=dict)
    mset_hist: dict[str, str] = Field(default_factory=dict)
