"""Benchmark: in-process (scipy + sklearn) DBSCAN vs. the subprocess-binary approach.

Run with the sklearn extra installed, e.g. from the monorepo root:

    uv run python packages/tools/benchmarks/dbscan_benchmark.py

It measures, on synthetic gene sets of increasing size:

  * ``sklearn run (ms)`` -- end-to-end time of the in-process ``SklearnDBSCAN`` variant
    (gene co-membership graph -> sparse eps-hop neighbour graph -> DBSCAN).
  * ``encode (ms)`` / ``argv bytes`` -- the cost the *subprocess* approach pays before the
    binary even starts: serialising the whole graph into one ``argv`` string, and that
    string's size. ``>256KB arg?`` flags when it crosses a typical single-argument limit
    (the total ARG_MAX on this machine is ~1 MB), at which point the binary call would fail.

Note: the compiled ``dbscan`` binary's own compute time is *not* measured here (it could
not be built in this environment); this quantifies the in-process variant's scaling and the
subprocess path's serialisation/ARG_MAX ceiling.
"""

from __future__ import annotations

import random
import time

from geneweaver.tools.dbscan import DBSCANInput, encode_bipartite
from geneweaver.tools.dbscan.sklearn_tool import SklearnDBSCAN

SINGLE_ARG_LIMIT = 256 * 1024  # conservative single-argument ceiling (macOS/Linux)

# (n_genes, n_gene_sets, genes_per_set)
SIZES = [
    (100, 20, 20),
    (500, 100, 30),
    (1000, 200, 40),
    (2000, 400, 50),
    (5000, 1000, 60),
    (10000, 2000, 80),
]


def make_gene_symbols(
    n_genes: int, n_sets: int, genes_per_set: int, seed: int = 0
) -> dict[str, list[str]]:
    """Synthetic gene sets: each set is a random sample from a shared gene pool."""
    rng = random.Random(seed)
    pool = [f"g{i}" for i in range(n_genes)]
    return {f"GS{s}": rng.sample(pool, min(genes_per_set, n_genes)) for s in range(n_sets)}


def main() -> None:
    """Run the benchmark and print a table."""
    header = f"{'genes':>6} {'sets':>5} {'g/set':>5} | {'sklearn run(ms)':>15} | {'encode(ms)':>10} {'argv bytes':>11} {'>256KB arg?':>11}"
    print(header)
    print("-" * len(header))
    for n_genes, n_sets, gps in SIZES:
        gene_symbols = make_gene_symbols(n_genes, n_sets, gps)
        tool_input = DBSCANInput(gene_symbols=gene_symbols, epsilon=2, min_points=3)

        start = time.perf_counter()
        out = SklearnDBSCAN().run(tool_input)
        run_ms = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        encoded, _, _ = encode_bipartite(gene_symbols)
        encode_ms = (time.perf_counter() - start) * 1000

        argv_bytes = len(encoded.encode())
        over = "YES" if argv_bytes > SINGLE_ARG_LIMIT else "no"
        print(
            f"{out.num_genes:>6} {n_sets:>5} {gps:>5} | {run_ms:>15.1f} | "
            f"{encode_ms:>10.2f} {argv_bytes:>11} {over:>11}"
        )


if __name__ == "__main__":
    main()
