"""Maximal k-partite cliques, as legacy's ``bk-partite`` binary finds them.

A line-for-line port of ``TOOLBOX/bk-partite`` (``bk.c: clique_find_v2``, the default
"Bron-Kerbosch version 2" with pivoting, and ``graph.c: read_graph``). Within a partite set
every pair of vertices is joined, as ``read_graph`` adds them, so a clique may hold several
vertices of each set; a clique counts only when it touches every partite set. Of the maximal
cliques found, two are kept as the binary keeps them: the one with the most vertices and the
one with the most edges between partite sets, each the *first* found on a tie. The
traversal -- vertex numbering, pivot choice, candidate order -- is the binary's, so ties
resolve the same way: checked against the compiled binary on real gene sets
(``tests/unit/test_triclique.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class KPartiteGraph:
    """Vertices numbered as ``read_graph`` numbers them, and their adjacency."""

    labels: list[str]
    part_of: list[int]
    parts: int
    adjacent: list[list[bool]]

    @classmethod
    def from_edges(
        cls, parts: int, edges: list[tuple[tuple[int, str], tuple[int, str]]]
    ) -> KPartiteGraph:
        """Number vertices by partite set, then by first appearance in ``edges``.

        :param edges: ``((part, label), (part, label))`` per edge, in file order.
        """
        order: list[dict[str, int]] = [{} for _ in range(parts)]
        for edge in edges:
            for part, label in edge:
                order[part].setdefault(label, len(order[part]))
        offsets = [sum(len(order[i]) for i in range(part)) for part in range(parts)]
        size = sum(len(o) for o in order)
        labels = [""] * size
        part_of = [0] * size
        for part, seen in enumerate(order):
            for label, index in seen.items():
                labels[offsets[part] + index] = label
                part_of[offsets[part] + index] = part
        adjacent = [[False] * size for _ in range(size)]
        for (pa, la), (pb, lb) in edges:
            u, v = offsets[pa] + order[pa][la], offsets[pb] + order[pb][lb]
            adjacent[u][v] = adjacent[v][u] = True
        # Every pair within a partite set (read_graph, without -intra).
        for part in range(parts):
            members = range(offsets[part], offsets[part] + len(order[part]))
            for u in members:
                for v in members:
                    if u != v:
                        adjacent[u][v] = True
        return cls(labels=labels, part_of=part_of, parts=parts, adjacent=adjacent)


@dataclass
class CliqueSearch:
    """What a search found: the two kept cliques, and how many maximal ones there were."""

    vertex_max: list[int] = field(default_factory=list)
    edge_max: list[int] = field(default_factory=list)
    edge_max_size: int = 0
    maximal: int = 0


def find_cliques(graph: KPartiteGraph, lower: int = 3, upper: int | None = None) -> CliqueSearch:
    """Run the binary's search over the whole graph (``maximal_clique`` with version 2)."""
    n = len(graph.labels)
    upper = n if upper is None else upper
    mask = (1 << graph.parts) - 1
    adjacent = graph.adjacent
    found = CliqueSearch()
    clique = [-1] * max(n, 1)

    def extend(old: list[int], lc: int, ne: int, ce: int) -> None:
        # Pivot: the vertex in old (not or cand) with fewest non-neighbours among cand.
        minnod, nod, fixp, s, pos = ce + 1, 0, 0, 0, 0
        for i in range(ce):
            count = 0
            p = old[i]
            for j in range(ne, ce):
                if not adjacent[p][old[j]]:
                    count += 1
                    pos = j
            if count < minnod:
                fixp, minnod = p, count
                if i < ne:
                    s = pos
                else:
                    s, nod = i, 1
        k = minnod + nod
        while k > 0:
            # Swap this candidate to be the next one.
            old[s], old[ne] = old[ne], old[s]
            u = old[ne]
            newx = [v for v in old[:ne] if adjacent[u][v]]
            new_ne = len(newx)
            newx += [v for v in old[ne + 1 : ce] if adjacent[u][v]]
            new_ce = len(newx)
            clique[lc] = u
            # Extend only if the clique and its candidates reach every partite set.
            bits = 0
            sizes = [0] * graph.parts
            for m in range(lc + 1):
                bits |= 1 << graph.part_of[clique[m]]
                sizes[graph.part_of[clique[m]]] += 1
            for m in range(new_ne, new_ce):
                bits |= 1 << graph.part_of[newx[m]]
            if bits == mask and lc + 1 <= upper:
                if new_ce == 0 and lc + 1 >= lower:
                    found.maximal += 1
                    if lc + 1 > len(found.vertex_max):
                        found.vertex_max = clique[: lc + 1]
                    edges = sum(
                        sizes[a] * sizes[b]
                        for a in range(graph.parts)
                        for b in range(a + 1, graph.parts)
                    )
                    if edges > found.edge_max_size:
                        found.edge_max_size = edges
                        found.edge_max = clique[: lc + 1]
                elif new_ne < new_ce:
                    extend(newx, lc + 1, new_ne, new_ce)
            # Move u to not.
            ne += 1
            # Bound: stop once the pivot neighbours every remaining candidate.
            if k > 1:
                s = ne
                while s < ce and adjacent[fixp][old[s]]:
                    s += 1
                if s == ce:
                    return
            k -= 1

    if n:
        extend(list(range(n)), 0, 0, n)
    return found


def by_part(graph: KPartiteGraph, clique: list[int]) -> list[list[str]]:
    """A clique's labels per partite set, in clique order, as ``print_clique_emax`` prints."""
    return [
        [graph.labels[v] for v in clique if graph.part_of[v] == part]
        for part in range(graph.parts)
    ]
