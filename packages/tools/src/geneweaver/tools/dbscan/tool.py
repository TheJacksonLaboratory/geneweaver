"""DBSCAN tool, reimplemented on the AbstractTool framework.

Ported from the legacy Celery worker ``legacy/tools-worker/tools/DBSCAN.py``, which shells
out to the compiled ``TOOLBOX/DBSCAN/dbscan`` C++ binary.

This is the first tool that wraps a compiled binary, so it establishes the pattern:

  - the *pure* parts (encoding the bipartite gene/gene-set graph into the binary's input
    string, and decoding the binary's JSON output back to gene symbols) are standalone,
    testable functions;
  - the *impure* part (invoking the binary) goes through an injectable ``runner``, so the
    tool can be unit-tested without the compiled binary, and the binary location is
    configurable for deployment.

Binary contract (from dbscanMain.cpp): ``dbscan <data> <epsilon> <minPts>`` where
``<data>`` is ``num_genes*num_genesets*num_links*<gene_idx>*<geneset_idx>*...``; stdout is
``@`` (no clusters) or a JSON 2D array of gene indices.

DB-backed species lookups in the legacy tool were presentation only and are dropped.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable

from geneweaver.tools.framework.abstract import AbstractTool

from .schema import DBSCANInput, DBSCANOutput

# A runner takes (encoded_data, epsilon, min_points) and returns the binary's raw stdout.
BinaryRunner = Callable[[str, float, int], str]

#: Env var that points at the compiled dbscan binary when no runner/path is supplied.
BINARY_ENV_VAR = "GENEWEAVER_DBSCAN_BINARY"


def encode_bipartite(
    gene_symbols: dict[str, list[str]],
) -> tuple[str, dict[str, int], dict[str, int]]:
    """Encode gene/gene-set co-membership into the dbscan binary's input string.

    :return: (encoded_data, gene_index, geneset_index) where the index maps assign each
        gene/gene-set a stable integer id. ``encoded_data`` is
        ``num_genes*num_genesets*num_links*<gene_idx>*<geneset_idx>*...``.
    """
    genes: dict[str, int] = {}
    genesets: dict[str, int] = {}
    links: list[str] = []
    for geneset_id, members in gene_symbols.items():
        gs_key = str(geneset_id)
        if gs_key not in genesets:
            genesets[gs_key] = len(genesets)
        for member in members:
            gene_key = str(member)
            if gene_key not in genes:
                genes[gene_key] = len(genes)
            links.append(f"{genes[gene_key]}*{genesets[gs_key]}")
    link_str = ("*".join(links) + "*") if links else ""
    encoded = f"{len(genes)}*{len(genesets)}*{len(links)}*{link_str}"
    return encoded, genes, genesets


def decode_clusters(raw_output: str, genes: dict[str, int]) -> list[list[str]]:
    """Decode the binary's JSON output (gene indices) back to gene symbols.

    ``@`` (or empty output) means no clusters were found.
    """
    raw = raw_output.strip()
    if not raw or raw == "@":
        return []
    index_to_gene = {idx: gene for gene, idx in genes.items()}
    clusters = json.loads(raw)
    return [[index_to_gene[int(g)] for g in cluster] for cluster in clusters]


def _subprocess_runner(binary_path: str) -> BinaryRunner:
    """Default runner: invoke the compiled dbscan binary via subprocess."""

    def run(encoded: str, epsilon: float, min_points: int) -> str:
        result = subprocess.run(
            [binary_path, encoded, str(epsilon), str(min_points)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"dbscan binary failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout

    return run


class DBSCAN(AbstractTool):
    """Cluster genes by gene-set co-membership using the DBSCAN C++ binary."""

    def __init__(self, binary_path: str | None = None, runner: BinaryRunner | None = None) -> None:
        """Configure how the dbscan binary is located/invoked.

        :param binary_path: path to the compiled dbscan binary (defaults to the
            ``GENEWEAVER_DBSCAN_BINARY`` env var).
        :param runner: an alternative callable to run the binary (used for testing); takes
            precedence over ``binary_path``.
        """
        self._binary_path = binary_path or os.environ.get(BINARY_ENV_VAR)
        self._runner = runner

    @property
    def tool_input(self) -> type[DBSCANInput]:
        """Input schema for the tool."""
        return DBSCANInput

    @property
    def tool_output(self) -> type[DBSCANOutput]:
        """Output schema for the tool."""
        return DBSCANOutput

    def _run_binary(self, encoded: str, epsilon: float, min_points: int) -> str:
        runner = self._runner
        if runner is None:
            if not self._binary_path:
                raise RuntimeError(
                    "dbscan binary not configured: set the "
                    f"{BINARY_ENV_VAR} env var, or pass binary_path/runner."
                )
            runner = _subprocess_runner(self._binary_path)
        return runner(encoded, epsilon, min_points)

    def run(self, tool_input: DBSCANInput) -> DBSCANOutput:
        """Cluster the genes; skip (ran=False) when there are too few for min_points."""
        encoded, genes, genesets = encode_bipartite(tool_input.gene_symbols)
        num_genes = len(genes)

        # Legacy gate: need at least min_points reachable neighbours.
        if num_genes - 1 < int(tool_input.min_points):
            return DBSCANOutput(
                ran=False, clusters=[], num_genes=num_genes, num_genesets=len(genesets)
            )

        raw = self._run_binary(encoded, tool_input.epsilon, int(tool_input.min_points))
        clusters = decode_clusters(raw, genes)
        return DBSCANOutput(
            ran=True,
            clusters=clusters,
            num_genes=num_genes,
            num_genesets=len(genesets),
        )
