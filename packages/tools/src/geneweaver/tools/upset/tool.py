"""UpSet tool, reimplemented on the AbstractTool framework.

Ported from the legacy Celery worker ``legacy/tools-worker/tools/UpSet.py`` (whose only
subprocess calls were commented-out cairosvg conversions, so it is pure-Python compute).

Ported: the UpSet intersection sizes -- for each combination of gene sets, the number of
genes belonging to *exactly* that combination. Dropped: SVG rendering (presentation). DB
homology resolution is the caller's responsibility (pass homology-keyed memberships).
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations

from geneweaver.tools.framework.abstract import AbstractTool

from .schema import UpSetInput, UpSetIntersection, UpSetOutput


def intersection_sizes(
    gene_memberships: dict[str, list[str]], include_zeros: bool = False
) -> list[UpSetIntersection]:
    """Count genes per exact gene-set combination (the UpSet plot data)."""
    # Each gene's "signature" is the set of gene sets it belongs to.
    gene_to_sets: dict[str, set[str]] = {}
    for gs_id, genes in gene_memberships.items():
        for gene in genes:
            gene_to_sets.setdefault(str(gene), set()).add(gs_id)

    counts: Counter[frozenset[str]] = Counter()
    for sets in gene_to_sets.values():
        counts[frozenset(sets)] += 1

    results = [
        UpSetIntersection(genesets=sorted(combo), size=size) for combo, size in counts.items()
    ]

    if include_zeros:
        present = set(counts)
        all_ids = list(gene_memberships)
        for r in range(1, len(all_ids) + 1):
            for combo in combinations(all_ids, r):
                if frozenset(combo) not in present:
                    results.append(UpSetIntersection(genesets=sorted(combo), size=0))

    results.sort(key=lambda x: (-x.size, x.genesets))
    return results


class UpSet(AbstractTool):
    """Compute UpSet intersection sizes across a set of gene sets."""

    @property
    def tool_input(self) -> type[UpSetInput]:
        """Input schema for the tool."""
        return UpSetInput

    @property
    def tool_output(self) -> type[UpSetOutput]:
        """Output schema for the tool."""
        return UpSetOutput

    def run(self, tool_input: UpSetInput) -> UpSetOutput:
        """Compute the per-combination intersection sizes."""
        return UpSetOutput(
            geneset_ids=tool_input.geneset_ids,
            include_homology=tool_input.include_homology,
            intersections=intersection_sizes(
                tool_input.gene_memberships, tool_input.include_zeros
            ),
        )
