"""Input/output schemas for the HyperGeometric (Fisher's exact) tool."""

from __future__ import annotations

from geneweaver.tools.framework.schema import ToolInput, ToolOutput
from pydantic import BaseModel, Field


class ContingencyCounts(BaseModel):
    """2x2 contingency table for a pair of gene sets (indices into ``geneset_ids``).

    Mirrors the legacy pairwise-deletion counts:
    ``f11`` = genes in both, ``f10`` = only in i, ``f01`` = only in j,
    ``f00`` = in neither (background).
    """

    i: int
    j: int
    f00: int
    f01: int
    f10: int
    f11: int


class HyperGeometricInput(ToolInput):
    """Input for the HyperGeometric tool (contingency counts resolved by the caller)."""

    geneset_ids: list[str] = Field(default_factory=list)
    pairs: list[ContingencyCounts] = Field(default_factory=list)


class HyperGeometricResult(BaseModel):
    """Fisher's exact test result for one gene-set pair.

    ``odds_ratio`` is None when it is infinite (a zero in the off-diagonal). ``hypergeometric``
    is the legacy one-tailed value: ``1 - upper_tail`` when the odds ratio is >1 or infinite,
    else ``1 - lower_tail``.
    """

    i: int
    j: int
    odds_ratio: float | None
    upper_tail: float
    lower_tail: float
    two_tailed: float
    hypergeometric: float


class HyperGeometricOutput(ToolOutput):
    """Per-pair Fisher's exact / hypergeometric results."""

    geneset_ids: list[str]
    results: list[HyperGeometricResult]
