"""Jaccard Similarity tool, reimplemented on the AbstractTool framework.

Ported from the legacy Celery worker ``legacy/tools-worker/tools/JaccardSimilarity.py``.

What was ported (the computation):
  - the Jaccard coefficient per gene-set pair: C / (A + B + C)
  - the empirical p-value (``jac_pvalue``): P(J_random >= J_observed) from a null
    distribution of Jaccard values for the two set sizes.

What was deliberately dropped:
  - venn-circle geometry and SVG/HTML rendering (presentation, belongs in the UI)
  - the unused ``factorial`` helper and the commented-out analytical p-value (dead code)

Decoupling (same pattern as the other ports): the legacy tool fetched/generated the null
distributions inside the task (DB lookup, falling back to the ``distribution_generator``
TOOLBOX binary). Generating those distributions is a data-layer/worker concern (like the
calculate_jaccard port); this pure tool *consumes* them via the input.
"""

from __future__ import annotations

from geneweaver.tools.framework.abstract import AbstractTool

from .schema import (
    JaccardDistribution,
    JaccardSimilarityInput,
    JaccardSimilarityOutput,
    JaccardSimilarityResult,
)

DistributionKey = tuple[int, int, bool]


def jaccard_coefficient(only_a: int, only_b: int, intersection: int) -> float:
    """Jaccard coefficient J = C / (A + B + C); 0.0 when there is no intersection."""
    if intersection == 0:
        return 0.0
    return float(intersection) / float(only_a + only_b + intersection)


def empirical_p_value(
    only_a: int,
    only_b: int,
    intersection: int,
    distributions: dict[DistributionKey, list[tuple[float, int]]],
    homology: bool,
) -> float:
    """Empirical p-value: fraction of the null distribution with Jaccard >= observed.

    Faithful to the legacy ``jac_pvalue``: identical sets give p=1; set sizes are sorted
    so ``A <= B``; a missing distribution yields 0.0 (the legacy generated it on the fly).
    """
    if only_a == 0 and only_b == 0:
        return 1.0
    a, b = (only_a, only_b) if only_a <= only_b else (only_b, only_a)

    frequencies = distributions.get((a, b, homology))
    if not frequencies:
        return 0.0

    n = a + b + intersection
    observed_j = float(intersection) / float(n)

    # +1 for the observation itself, as in the legacy implementation.
    at_least_as_extreme = 1
    total = 1
    for jaccard_value, frequency in frequencies:
        if jaccard_value >= observed_j:
            at_least_as_extreme += frequency
        total += frequency
    return float(at_least_as_extreme) / total


def _index_distributions(
    distributions: list[JaccardDistribution],
) -> dict[DistributionKey, list[tuple[float, int]]]:
    return {(d.set_size1, d.set_size2, d.homology): d.frequencies for d in distributions}


class JaccardSimilarity(AbstractTool):
    """Pairwise Jaccard coefficients + empirical p-values across a set of gene sets."""

    @property
    def tool_input(self) -> type[JaccardSimilarityInput]:
        """Input schema for the tool."""
        return JaccardSimilarityInput

    @property
    def tool_output(self) -> type[JaccardSimilarityOutput]:
        """Output schema for the tool."""
        return JaccardSimilarityOutput

    def run(self, tool_input: JaccardSimilarityInput) -> JaccardSimilarityOutput:
        """Compute Jaccard coefficient + empirical p-value for each provided pair."""
        distributions = _index_distributions(tool_input.distributions)
        results: list[JaccardSimilarityResult] = []
        for pair in tool_input.pairs:
            jac = jaccard_coefficient(pair.only_i, pair.only_j, pair.intersection)
            if pair.intersection == 0:
                p_value: float | None = None
            else:
                p_value = empirical_p_value(
                    pair.only_i,
                    pair.only_j,
                    pair.intersection,
                    distributions,
                    tool_input.include_homology,
                )
            results.append(
                JaccardSimilarityResult(
                    i=pair.i,
                    j=pair.j,
                    jaccard=jac,
                    p_value=p_value,
                    intersection=pair.intersection,
                    only_i=pair.only_i,
                    only_j=pair.only_j,
                )
            )

        return JaccardSimilarityOutput(
            geneset_ids=tool_input.geneset_ids,
            include_homology=tool_input.include_homology,
            p_value_threshold=tool_input.p_value_threshold,
            results=results,
        )
