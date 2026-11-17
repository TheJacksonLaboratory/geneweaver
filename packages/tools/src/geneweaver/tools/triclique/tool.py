"""Triclique, legacy's TricliqueViewer, reimplemented on the AbstractTool framework.

Legacy (``legacy/src/tools/tricliqueblueprint.py``, ``legacy/src/edgelist.py`` and the
``TricliqueViewer`` worker) built a three-part graph from two *projects* -- gene sets of
project A, gene sets of project B, and the genes both projects hold -- wrote it as a ``.kel``
edge list, ran the ``bk-partite`` binary over it, and kept the "edge maximum k-clique". It
was disabled in legacy (``tool_active = 0``) and never ran on dev; its worker was a stub and
its JSON/CSV output an unfinished TODO.

Ported here, with two groups of gene sets in place of projects (v3 has none yet):

- the graph, as legacy's ``create_kpartite_file_from_gene_intersection`` builds it: a gene
  set of either group linked to each shared gene it holds; a gene set of A linked to one of
  B when they share any gene; no more than 50 shared genes, as legacy refused;
- the search, as a Python port of ``bk-partite`` (`kpartite`), which returns the same
  cliques as the binary, ties included.

Not ported: legacy's "Jaccard overlap" method (three or more projects), and its
``1/gs_count`` chord matrix, which was unfinished.
"""

from __future__ import annotations

from geneweaver.tools.framework.abstract import AbstractTool

from . import kpartite
from .schema import MAX_SHARED_GENES, Triclique, TricliqueInput, TricliqueOutput

#: Partite sets, in legacy's .kel column order.
A, B, GENES = 0, 1, 2


def tripartite_edges(tool_input: TricliqueInput) -> tuple[list[str], list]:
    """The shared genes, and the graph's edges in a fixed order (legacy's set order varied).

    :raises ValueError: If the groups share more than `MAX_SHARED_GENES` genes.
    """
    genes = {
        gs: set(tool_input.gene_memberships.get(gs, []))
        for gs in tool_input.group_a + tool_input.group_b
    }
    in_a = set().union(*(genes[gs] for gs in tool_input.group_a))
    in_b = set().union(*(genes[gs] for gs in tool_input.group_b))
    shared = sorted(in_a & in_b)
    if len(shared) > MAX_SHARED_GENES:
        raise ValueError(
            f"The two groups share {len(shared)} genes; Triclique takes at most "
            f"{MAX_SHARED_GENES}, as legacy did. Use smaller gene sets, or a threshold."
        )
    edges = []
    for part, group in ((A, tool_input.group_a), (B, tool_input.group_b)):
        for gs in group:
            for gene in shared:
                if gene in genes[gs]:
                    edges.append(((part, gs), (GENES, gene)))
    for gs_a in tool_input.group_a:
        for gs_b in tool_input.group_b:
            if genes[gs_a] & genes[gs_b]:
                edges.append(((A, gs_a), (B, gs_b)))
    return shared, edges


def _triclique(graph: kpartite.KPartiteGraph, clique: list[int]) -> Triclique | None:
    if not clique:
        return None
    group_a, group_b, genes = kpartite.by_part(graph, clique)
    return Triclique(
        group_a=group_a,
        group_b=group_b,
        genes=genes,
        edges=len(group_a) * len(group_b) + (len(group_a) + len(group_b)) * len(genes),
    )


def find_tricliques(tool_input: TricliqueInput) -> TricliqueOutput:
    """Build the graph and keep the maximum tricliques."""
    shared, edges = tripartite_edges(tool_input)
    graph = kpartite.KPartiteGraph.from_edges(3, edges)
    found = kpartite.find_cliques(graph) if edges else kpartite.CliqueSearch()
    return TricliqueOutput(
        group_a=list(tool_input.group_a),
        group_b=list(tool_input.group_b),
        include_homology=tool_input.include_homology,
        shared_genes=shared,
        maximal_tricliques=found.maximal,
        edge_maximum=_triclique(graph, found.edge_max),
        vertex_maximum=_triclique(graph, found.vertex_max),
    )


class TricliqueTool(AbstractTool):
    """The largest clique across two groups of gene sets and their shared genes."""

    @property
    def tool_input(self) -> type[TricliqueInput]:
        """Input schema for the tool."""
        return TricliqueInput

    @property
    def tool_output(self) -> type[TricliqueOutput]:
        """Output schema for the tool."""
        return TricliqueOutput

    def run(self, tool_input: TricliqueInput) -> TricliqueOutput:
        """Find the maximum tricliques."""
        return find_tricliques(tool_input)
