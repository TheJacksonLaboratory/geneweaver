r"""PhenomeMap tool, reimplemented on the AbstractTool framework.

Ported from the legacy Celery worker ``legacy/tools-worker/tools/PhenomeMap.py``, which
shelled out to the ``TOOLBOX/biclique_tool/biclique`` and ``TOOLBOX/bstrap/bstrap`` binaries
and emitted dot/graphml/svg/pdf/csv/json renderings.

What is ported (the genuine, reusable compute):

  - ``build_edge_list`` -- encode the bipartite gene / gene-set graph into the biclique
    binary's edge-list input (pure);
  - the maximal-biclique enumeration itself, via an injectable ``biclique_runner`` (the
    binary-wrapper pattern, same as DBSCAN/MSET);
  - ``parse_bicliques`` -- decode the binary's 3-line-per-biclique stdout (pure);
  - the subset-relationship + link-scoring pass (``similarity``), the p-value / FDR link
    trim, the cut-depth computation, and the unconnected-node trim (all pure);
  - an optional bootstrap reduction for large graphs, via an injectable ``bootstrap_runner``.

What is dropped: every rendering path (dot/graphml/svg/pdf/csv/json, graphviz ``dot``), and
the DB lookups that only fed labels/tooltips/colors (gene symbols, species, publications,
abbreviations). The permutation-significance add-on (the ``bicliquer`` binary over an
``.odemat`` matrix) is out of scope for this port -- it is a separate statistic with a
different input encoding and can be added later as another injectable runner.

Improvement vs legacy: the link score's Kolmogorov-Smirnov term uses
``scipy.stats.ks_2samp`` (well-tested, C-backed) instead of the legacy hand-rolled KS
approximation. scipy is only imported when gene ranks are supplied (the ``sklearn`` extra).

biclique binary contract (from biclique-driver.c): ``biclique <edgelist_file> -p`` prints,
per biclique, three lines -- tab-joined gene-set ids, tab-joined gene ids, then a blank line.
The edge-list file's first line is ``<num_genes>\t<num_genesets>\t<num_edges>`` followed by
one ``<gene_id>\t<geneset_id>`` per edge.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from geneweaver.tools.framework.abstract import AbstractTool

from .schema import (
    BicliqueLink,
    BicliqueNode,
    PhenomeMapInput,
    PhenomeMapOutput,
)

#: Runner: takes the edge-list text, returns the biclique binary's raw stdout.
BicliqueRunner = Callable[[str], str]
#: Runner: takes the ``.bic`` text, returns (displayed biclique indices, edge weights by
#: index pair). Indices are the biclique's position in the ``.bic`` file.
BootstrapRunner = Callable[[str], "tuple[set[int], dict[tuple[int, int], float]]"]

BICLIQUE_BINARY_ENV_VAR = "GENEWEAVER_BICLIQUE_BINARY"
BOOTSTRAP_BINARY_ENV_VAR = "GENEWEAVER_BSTRAP_BINARY"


@dataclass
class _Biclique:
    """Internal working node during graph construction (converted to BicliqueNode at the end)."""

    id: int
    genesets: frozenset[str]
    genes: list[str]
    ranks: list[float]
    emphasize: bool = False
    displayed: bool = True
    # id -> link score
    parents: dict[int, float] = field(default_factory=dict)
    children: dict[int, float] = field(default_factory=dict)

    @property
    def num_genes(self) -> int:
        """Number of genes shared across this biclique's gene sets."""
        return len(self.genes)

    @property
    def size(self) -> int:
        """Number of gene sets in this biclique."""
        return len(self.genesets)


# --------------------------------------------------------------------------- pure helpers


def build_edge_list(gene_sets: dict[str, list[str]]) -> tuple[str, int, int]:
    """Encode the bipartite graph into the biclique binary's edge-list text.

    :return: (edge_list_text, num_genes, num_genesets).
    """
    genes: dict[str, None] = {}
    edges: list[tuple[str, str]] = []
    for geneset_id, members in gene_sets.items():
        gs = str(geneset_id)
        for member in members:
            g = str(member)
            genes.setdefault(g, None)
            edges.append((g, gs))
    num_genes = len(genes)
    num_genesets = len(gene_sets)
    lines = [f"{num_genes}\t{num_genesets}\t{len(edges)}"]
    lines.extend(f"{g}\t{gs}" for g, gs in edges)
    return "\n".join(lines) + "\n", num_genes, num_genesets


def parse_bicliques(raw_output: str) -> list[tuple[frozenset[str], list[str]]]:
    """Decode the biclique binary's stdout into (gene-set ids, gene ids) pairs.

    The binary prints three lines per biclique: tab-joined gene-set ids, tab-joined gene
    ids, then a blank line.
    """
    bicliques: list[tuple[frozenset[str], list[str]]] = []
    genesets: frozenset[str] | None = None
    for line_num, raw in enumerate(raw_output.splitlines(), start=1):
        pos = line_num % 3
        if pos == 0:  # blank separator line
            continue
        fields = raw.strip().split("\t")
        if pos == 1:  # gene-set ids
            genesets = frozenset(f for f in fields if f)
        else:  # pos == 2: gene ids
            genes = [g for g in fields if g]
            bicliques.append((genesets or frozenset(), genes))
    return bicliques


def similarity(parent: _Biclique, child: _Biclique) -> float:
    """Score a parent->child link: gene-count ratio times a KS p-value over gene ranks.

    Faithful to the legacy ``similarity()``: ``(parent_genes / child_genes) * ks_pvalue``.
    When either side has no ranks, the KS term is 1.0 (the ratio alone), avoiding scipy.
    """
    ratio = parent.num_genes / child.num_genes if child.num_genes else 0.0
    if not parent.ranks or not child.ranks:
        return ratio
    try:
        from scipy.stats import ks_2samp
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "PhenomeMap link scoring with gene ranks requires the 'sklearn' extra "
            "(for scipy): pip install geneweaver-tools[sklearn]"
        ) from exc
    ks_pvalue = float(ks_2samp(parent.ranks, child.ranks).pvalue)
    return ks_pvalue * ratio


def _fdr_threshold(scores: list[float], p_value_threshold: float) -> float:
    """Benjamini-Hochberg threshold derived from the link scores (numpy-free)."""
    n = len(scores)
    if n == 0:
        return p_value_threshold
    ordered = sorted(scores)
    step = (p_value_threshold - p_value_threshold / n) / (n - 1) if n > 1 else 0.0
    for i, p in enumerate(ordered):
        line = p_value_threshold / n + step * i
        if p > line:
            return line
    return p_value_threshold


def find_cut_depth(by_size: list[tuple[int, list[_Biclique]]], max_level: int) -> tuple[int, int]:
    """Find the size below which to cut the tree to keep it manageable.

    Mirrors the legacy ``find_cut_depth``: scanning sizes largest-first (excluding the
    smallest), the cut is set to the largest size whose displayed-node count exceeds
    ``max_level``. Returns (total_displayed_above_smallest, cut_depth).
    """
    if max_level == 0:
        total = sum(len(lst) for _, lst in by_size)
        return total, 0
    cut_depth = 0
    total = 0
    for size, lst in reversed(by_size[1:]):
        level_count = sum(1 for b in lst if b.displayed)
        total += level_count
        if level_count > max_level:
            cut_depth = size
    return total, cut_depth


def compute_subset_links(by_size: list[tuple[int, list[_Biclique]]]) -> list[float]:
    """Link each biclique to its immediate descendant bicliques and score the links.

    A biclique B is an immediate child of A when B's gene sets are a proper subset of A's
    and B is not already covered by a closer child of A (transitive reduction). Populates
    ``parents``/``children`` (id -> score) in place; returns all link scores.
    """
    by_id = {b.id: b for _, lst in by_size for b in lst}
    scores: list[float] = []
    for i in range(1, len(by_size)):
        for parent in by_size[i][1]:
            covered: set[int] = set()
            for j in range(i - 1, -1, -1):
                for child in by_size[j][1]:
                    if child.genesets < parent.genesets:
                        if child.id not in covered:
                            sim = similarity(parent, child)
                            parent.children[child.id] = sim
                            child.parents[parent.id] = sim
                            covered.add(child.id)
                            scores.append(sim)
                        covered |= set(child.children)
    # by_id retained for symmetry / potential callers; links are stored on the objects.
    del by_id
    return scores


def trim_links_by_score(
    by_size: list[tuple[int, list[_Biclique]]],
    scores: list[float],
    p_value_threshold: float,
    use_fdr: bool,
) -> None:
    """Drop parent links whose score exceeds the (optionally FDR-corrected) threshold."""
    if p_value_threshold >= 0.99999:
        return
    threshold = _fdr_threshold(scores, p_value_threshold) if use_fdr else p_value_threshold
    by_id = {b.id: b for _, lst in by_size for b in lst}
    for _, lst in by_size[:-1]:
        for b in lst:
            to_remove = [pid for pid, sim in b.parents.items() if sim > threshold]
            for pid in to_remove:
                del b.parents[pid]
                by_id[pid].children.pop(b.id, None)


def trim_unconnected(
    by_size: list[tuple[int, list[_Biclique]]], cut_depth: int
) -> list[tuple[int, list[_Biclique]]]:
    """Remove sizes at/below the cut and nodes that are hidden or have no links."""
    result: list[tuple[int, list[_Biclique]]] = []
    for size, lst in by_size:
        if size <= cut_depth:
            continue
        kept = [b for b in lst if b.displayed and (b.parents or b.children)]
        if kept:
            result.append((size, kept))
    return result


# --------------------------------------------------------------------------- runners


def _subprocess_biclique_runner(binary_path: str) -> BicliqueRunner:
    """Default biclique runner: write the edge list to a temp file and run the binary."""

    def run(edge_list_text: str) -> str:
        workdir = tempfile.mkdtemp(prefix="phenomemap_")
        el_path = os.path.join(workdir, "graph.el")
        with open(el_path, "w") as handle:
            handle.write(edge_list_text)
        result = subprocess.run(
            [binary_path, el_path, "-p"], capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"biclique binary failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout

    return run


# --------------------------------------------------------------------------- the tool


class PhenomeMap(AbstractTool):
    """Build the maximal-biclique intersection graph of a set of gene sets."""

    def __init__(
        self,
        biclique_binary_path: str | None = None,
        biclique_runner: BicliqueRunner | None = None,
        bootstrap_binary_path: str | None = None,
        bootstrap_runner: BootstrapRunner | None = None,
    ) -> None:
        """Configure how the biclique (and optional bootstrap) binaries are run.

        Pass ``*_runner`` callables to unit-test without the compiled binaries; otherwise the
        binary paths (or the ``GENEWEAVER_BICLIQUE_BINARY`` / ``GENEWEAVER_BSTRAP_BINARY``
        env vars) are used. Bootstrap is optional: without a runner/path it is skipped.
        """
        self._biclique_binary_path = biclique_binary_path or os.environ.get(
            BICLIQUE_BINARY_ENV_VAR
        )
        self._biclique_runner = biclique_runner
        self._bootstrap_binary_path = bootstrap_binary_path or os.environ.get(
            BOOTSTRAP_BINARY_ENV_VAR
        )
        self._bootstrap_runner = bootstrap_runner

    @property
    def tool_input(self) -> type[PhenomeMapInput]:
        """Input schema for the tool."""
        return PhenomeMapInput

    @property
    def tool_output(self) -> type[PhenomeMapOutput]:
        """Output schema for the tool."""
        return PhenomeMapOutput

    def _run_biclique(self, edge_list_text: str) -> str:
        runner = self._biclique_runner
        if runner is None:
            if not self._biclique_binary_path:
                raise RuntimeError(
                    f"biclique binary not configured: set {BICLIQUE_BINARY_ENV_VAR}, or "
                    "pass biclique_binary_path/biclique_runner."
                )
            runner = _subprocess_biclique_runner(self._biclique_binary_path)
        return runner(edge_list_text)

    def _maybe_bootstrap(
        self, by_size: list[tuple[int, list[_Biclique]]], displayed_total: int, tool_input
    ) -> bool:
        """Apply bootstrap reduction on large graphs if a runner/binary is available."""
        if tool_input.disable_bootstrap:
            return False
        if displayed_total <= tool_input.bootstrap_node_threshold:
            return False
        runner = self._bootstrap_runner
        if runner is None and self._bootstrap_binary_path:
            runner = self._subprocess_bootstrap_runner(self._bootstrap_binary_path)
        if runner is None:
            return False

        index_to_biclique: dict[int, _Biclique] = {}
        lines: list[str] = []
        idx = 0
        for _, lst in by_size:
            for b in lst:
                lines.append("\t".join(b.genes))
                lines.append("\t".join(sorted(b.genesets)))
                b.displayed = False
                index_to_biclique[idx] = b
                idx += 1
        displayed_indices, _edges = runner("\n".join(lines) + "\n")
        for i in displayed_indices:
            if i in index_to_biclique:
                index_to_biclique[i].displayed = True
        return True

    @staticmethod
    def _subprocess_bootstrap_runner(binary_path: str) -> BootstrapRunner:
        """Default bootstrap runner: 1000 iterations, 75% sampling (legacy parameters)."""

        def run(bic_text: str) -> tuple[set[int], dict[tuple[int, int], float]]:
            workdir = tempfile.mkdtemp(prefix="phenomemap_bstrap_")
            bic_path = os.path.join(workdir, "graph.bic")
            with open(bic_path, "w") as handle:
                handle.write(bic_text)
            proc = subprocess.run(
                [binary_path, bic_path, "x", "-i", "1000 0.75", "-t", "12"],
                capture_output=True,
                text=True,
                check=False,
            )
            displayed: set[int] = set()
            edges: dict[tuple[int, int], float] = {}
            reading_nodes = True
            for raw in proc.stderr.splitlines():
                e = raw.strip()
                if e == "":
                    reading_nodes = not reading_nodes
                    continue
                if reading_nodes:
                    displayed.add(int(e))
                else:
                    parts = e.split("\t")
                    if len(parts) >= 3:
                        edges[(int(parts[0]), int(parts[1]))] = float(parts[2])
            return displayed, edges

        return run

    def run(self, tool_input: PhenomeMapInput) -> PhenomeMapOutput:
        """Build the intersection graph of the input gene sets."""
        edge_list_text, num_genes, num_genesets = build_edge_list(tool_input.gene_sets)
        raw = self._run_biclique(edge_list_text)

        emphasis = {str(g) for g in tool_input.emphasis_genes}
        check_emphasis = bool(emphasis)

        # Build working bicliques, grouped by gene-set count (size), filtering tiny ones.
        by_size_map: dict[int, list[_Biclique]] = defaultdict(list)
        next_id = 0
        for genesets, genes in parse_bicliques(raw):
            if len(genes) < tool_input.min_genes:
                continue
            next_id += 1
            emphasize = (not check_emphasis) or any(g in emphasis for g in genes)
            ranks = [tool_input.gene_ranks[g] for g in genes if g in tool_input.gene_ranks]
            by_size_map[len(genesets)].append(
                _Biclique(
                    id=next_id,
                    genesets=genesets,
                    genes=genes,
                    ranks=ranks,
                    emphasize=emphasize,
                )
            )

        notes: list[str] = []
        if not by_size_map:
            return PhenomeMapOutput(
                nodes=[],
                num_genes=num_genes,
                num_genesets=num_genesets,
                cut_depth=0,
                notes=["No bicliques met the minimum gene threshold."],
            )

        by_size = sorted(by_size_map.items(), key=lambda kv: kv[0])

        displayed_total, cut_depth = find_cut_depth(by_size, tool_input.max_level)
        if cut_depth:
            notes.append(
                f"Tree cut below size {cut_depth} to keep the result manageable "
                f"(max_level={tool_input.max_level})."
            )

        bootstrap_applied = self._maybe_bootstrap(by_size, displayed_total, tool_input)
        if bootstrap_applied:
            notes.append("Bootstrap reduction applied (large graph).")
            displayed_total, cut_depth = find_cut_depth(by_size, tool_input.max_level)

        scores = compute_subset_links(by_size)
        trim_links_by_score(by_size, scores, tool_input.p_value_threshold, tool_input.use_fdr)
        by_size = trim_unconnected(by_size, cut_depth)

        if not by_size:
            return PhenomeMapOutput(
                nodes=[],
                num_genes=num_genes,
                num_genesets=num_genesets,
                cut_depth=cut_depth,
                bootstrap_applied=bootstrap_applied,
                notes=[*notes, "No connected bicliques remained after trimming."],
            )

        # Links may still reference bicliques that were cut (size <= cut_depth) or trimmed
        # as unconnected; restrict parents/children to the surviving nodes so the emitted
        # graph has no dangling edges (the legacy tool filters these at output time).
        surviving = {b.id for _, lst in by_size for b in lst}

        # Depth: largest gene-set count = depth 0, descending by size.
        nodes: list[BicliqueNode] = []
        for depth, (_, lst) in enumerate(reversed(by_size)):
            for b in lst:
                nodes.append(
                    BicliqueNode(
                        id=b.id,
                        genesets=sorted(b.genesets),
                        genes=list(b.genes),
                        depth=depth,
                        displayed=b.displayed,
                        emphasize=b.emphasize,
                        parents=sorted(pid for pid in b.parents if pid in surviving),
                        children=[
                            BicliqueLink(target=cid, score=score)
                            for cid, score in sorted(b.children.items())
                            if cid in surviving
                        ],
                    )
                )

        return PhenomeMapOutput(
            nodes=nodes,
            num_genes=num_genes,
            num_genesets=num_genesets,
            cut_depth=cut_depth,
            bootstrap_applied=bootstrap_applied,
            notes=notes,
        )
