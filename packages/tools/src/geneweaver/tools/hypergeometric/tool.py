"""HyperGeometric tool (Fisher's exact test), reimplemented on the AbstractTool framework.

Ported from the legacy Celery worker ``legacy/tools-worker/tools/HyperGeometric.py``.

Ported: the Fisher's exact test over each gene-set pair's 2x2 contingency table
(odds ratio + upper/lower/two-tailed p-values), and the legacy "hg" one-tailed value.

Dropped: venn-circle geometry + SVG rendering (presentation).

Two deliberate improvements over the legacy (it said "updates/improvements"):
  - Binomial coefficients use ``math.comb`` (exact integers) instead of the legacy
    incremental float ``combtl`` (which lost precision for large counts).
  - **Bug fix**: the legacy ``fisher`` set ``pval = prob`` *once* before the ut/lt/tt loop,
    so the three tail p-values accumulated instead of resetting — making lt/tt wrong. Here
    each tail is computed independently (standard Fisher's exact). This changes numeric
    output vs. the legacy; that was a defect, not intended behaviour.
"""

from __future__ import annotations

import math

from geneweaver.tools.framework.abstract import AbstractTool

from .schema import (
    ContingencyCounts,
    HyperGeometricInput,
    HyperGeometricOutput,
    HyperGeometricResult,
)


def fisher_exact_2x2(
    f00: int, f01: int, f10: int, f11: int
) -> tuple[float | None, float, float, float]:
    """Fisher's exact test on a 2x2 table.

    :return: (odds_ratio, upper_tail, lower_tail, two_tailed). ``odds_ratio`` is None when
        infinite (an off-diagonal zero).
    """
    odds_den = f01 * f10
    odds_ratio = None if odds_den == 0 else (f00 * f11) / odds_den

    f0 = f00 + f01
    g0 = f00 + f10
    g1 = f01 + f11
    ft = f00 + f01 + f10 + f11

    total = math.comb(ft, f0)
    observed_p = (math.comb(g0, f00) * math.comb(g1, f01)) / total

    def tail(a_start: int, a_end: int) -> float:
        # Each tail starts from the observed probability and adds the configurations in
        # range that are at least as extreme (p < observed). Reset per tail (legacy bug fix).
        pval = observed_p
        for a in range(int(a_start), int(a_end) + 1):
            if a == f00:
                continue
            b = f0 - a
            c = g0 - a
            d = g1 - b
            if d < 0:
                continue
            p = (math.comb(a + c, a) * math.comb(b + d, b)) / total
            if p < observed_p:
                pval += p
        return min(pval, 1.0)

    a_max = min(f0, g0)
    upper = tail(f00 + 1, a_max)
    lower = tail(0, f00 - 1)
    two_tailed = tail(0, a_max)
    return odds_ratio, upper, lower, two_tailed


def _result_for_pair(pair: ContingencyCounts) -> HyperGeometricResult:
    odds_ratio, upper, lower, two_tailed = fisher_exact_2x2(pair.f00, pair.f01, pair.f10, pair.f11)
    # Legacy "hg": use the upper tail when the odds ratio is >1 or infinite, else lower.
    use_upper = odds_ratio is None or odds_ratio > 1.0
    hypergeometric = 1.0 - upper if use_upper else 1.0 - lower
    return HyperGeometricResult(
        i=pair.i,
        j=pair.j,
        odds_ratio=odds_ratio,
        upper_tail=upper,
        lower_tail=lower,
        two_tailed=two_tailed,
        hypergeometric=hypergeometric,
    )


class HyperGeometric(AbstractTool):
    """Fisher's exact / hypergeometric enrichment test across gene-set pairs."""

    @property
    def tool_input(self) -> type[HyperGeometricInput]:
        """Input schema for the tool."""
        return HyperGeometricInput

    @property
    def tool_output(self) -> type[HyperGeometricOutput]:
        """Output schema for the tool."""
        return HyperGeometricOutput

    def run(self, tool_input: HyperGeometricInput) -> HyperGeometricOutput:
        """Compute Fisher's exact results for each provided gene-set pair."""
        return HyperGeometricOutput(
            geneset_ids=tool_input.geneset_ids,
            results=[_result_for_pair(pair) for pair in tool_input.pairs],
        )
