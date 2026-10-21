"""GeneSet Graph, reimplemented on the AbstractTool framework.

Ported from the legacy Celery worker ``legacy/tools-worker/tools/GeneSetViewer.py``
("GeneSet Graph" in legacy's tool list). Legacy built a graphviz ``dot`` file -- gene sets on
one side, the genes they hold on the other, genes ranked by how many gene sets hold them --
and rendered it to SVG and PDF with ``dot``. Ported: the graph itself and legacy's degree
rules and statistics. Dropped: the ``dot`` rendering, which the UI draws instead.

Fixed against legacy: the average degree divided by zero for gene sets with no genes, and the
gene set colour index read an `i` left over from an earlier loop (legacy's own TODO).
"""

from __future__ import annotations

from collections import Counter

from geneweaver.tools.framework.abstract import AbstractTool

from .schema import (
    GenesetGraphGene,
    GenesetGraphInput,
    GenesetGraphOutput,
    GenesetGraphSet,
)


def auto_min_degree(degree_counts: Counter[int]) -> int:
    """Legacy's "Auto" minimum degree.

    Walk degrees from the highest down to 2, totalling the genes passed; at every degree
    holding more than 25 genes once more than 4 genes have been passed, the cut moves to just
    above it. So the last such degree on the way down wins, and with none the cut is 2.
    Kept exactly as legacy computed it, including that the cut can move more than once.
    """
    max_degree = max(degree_counts, default=0)
    chosen: int | None = None
    passed = 0
    for degree in range(max_degree, 1, -1):
        if degree_counts.get(degree, 0) > 25 and passed > 4:
            chosen = degree + 1
        else:
            passed += degree_counts.get(degree, 0)
    return 2 if chosen is None else chosen


def build_graph(tool_input: GenesetGraphInput) -> GenesetGraphOutput:
    """The gene sets, the genes drawn, and the degree statistics."""
    ids = [str(gs_id) for gs_id in tool_input.geneset_ids] or list(tool_input.gene_memberships)
    holders: dict[str, list[str]] = {}
    for gs_id in ids:
        for gene in dict.fromkeys(tool_input.gene_memberships.get(gs_id, [])):
            holders.setdefault(str(gene), []).append(gs_id)

    degrees = {gene: len(sets) for gene, sets in holders.items()}
    degree_counts = Counter(degrees.values())
    min_degree = (
        auto_min_degree(degree_counts)
        if tool_input.min_degree == "auto"
        else int(tool_input.min_degree)
    )

    emphasis = {gene.lower() for gene in tool_input.emphasis_genes}
    drawn = [
        GenesetGraphGene(
            symbol=gene,
            degree=degrees[gene],
            genesets=sets,
            emphasized=gene.lower() in emphasis,
        )
        for gene, sets in holders.items()
        if degrees[gene] >= min_degree
    ]
    drawn.sort(key=lambda gene: (-gene.degree, gene.symbol.lower()))

    drawn_per_set = Counter(gs_id for gene in drawn for gs_id in gene.genesets)
    sizes = {gs_id: len(set(tool_input.gene_memberships.get(gs_id, []))) for gs_id in ids}
    # Legacy listed every gene set holding any gene; "suppress disconnected" kept only those
    # with a drawn gene. A gene set with no genes was never drawn.
    shown = [
        gs_id
        for gs_id in ids
        if sizes[gs_id] > 0 and (drawn_per_set[gs_id] > 0 or not tool_input.suppress_disconnected)
    ]
    return GenesetGraphOutput(
        geneset_ids=ids,
        include_homology=tool_input.include_homology,
        min_degree=min_degree,
        genesets=[
            GenesetGraphSet(id=gs_id, genes=drawn_per_set[gs_id], size=sizes[gs_id])
            for gs_id in shown
        ],
        genes=drawn,
        total_genes=len(degrees),
        min_gene_degree=min(degrees.values(), default=0),
        max_gene_degree=max(degrees.values(), default=0),
        avg_gene_degree=(sum(degrees.values()) / len(degrees)) if degrees else 0.0,
    )


class GenesetGraph(AbstractTool):
    """Draw gene sets and the genes they share (legacy GeneSetViewer)."""

    @property
    def tool_input(self) -> type[GenesetGraphInput]:
        """Input schema for the tool."""
        return GenesetGraphInput

    @property
    def tool_output(self) -> type[GenesetGraphOutput]:
        """Output schema for the tool."""
        return GenesetGraphOutput

    def run(self, tool_input: GenesetGraphInput) -> GenesetGraphOutput:
        """Build the graph."""
        return build_graph(tool_input)
