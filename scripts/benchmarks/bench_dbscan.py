"""DBSCAN: the legacy C++ binary vs. the in-process SklearnDBSCAN variant.

Answers "is the Python (scipy+sklearn) DBSCAN necessary/better than the original binary?"
on two axes:

  - **agreement**: do they produce the same clusters on a real graph? (the binary uses a
    custom BFS regionQuery + expandCluster; sklearn uses standard density-reachability);
  - **speed**: end-to-end wall time on synthetic gene sets of increasing size, including
    the subprocess path's encode + argv-serialisation overhead the binary pays.

Usage:
    GENEWEAVER_DBSCAN_BINARY=/tmp/dbscan_build/dbscan \
    [GENEWEAVER_DBSCAN_GRAPH_JSON=/tmp/dbscan_graph.json] \
    uv run --extra sklearn --project packages/tools python scripts/benchmarks/bench_dbscan.py
"""
# ruff: noqa: D103  (benchmark script; transcribed legacy code)

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "tools", "src"))
from geneweaver.tools.dbscan import DBSCANInput, decode_clusters, encode_bipartite
from geneweaver.tools.dbscan.sklearn_tool import SklearnDBSCAN

BINARY = os.environ["GENEWEAVER_DBSCAN_BINARY"]


def make_gene_symbols(n_genes, n_sets, genes_per_set, seed=0):
    """Synthetic gene sets: each set a random sample from a shared gene pool."""
    rng = random.Random(seed)
    pool = [f"g{i}" for i in range(n_genes)]
    return {f"GS{s}": rng.sample(pool, min(genes_per_set, n_genes)) for s in range(n_sets)}


def as_clusters(clusters):
    return {frozenset(c) for c in clusters}


def run_binary(gene_symbols, epsilon, min_pts):
    """Time the binary path end-to-end (encode + subprocess + decode)."""
    t0 = time.perf_counter()
    encoded, genes, _ = encode_bipartite(gene_symbols)
    r = subprocess.run(
        [BINARY, encoded, str(epsilon), str(min_pts)], capture_output=True, text=True, check=True
    )
    clusters = decode_clusters(r.stdout, genes)
    return clusters, (time.perf_counter() - t0) * 1000


def run_sklearn(gene_symbols, epsilon, min_pts):
    """Time the in-process SklearnDBSCAN end-to-end."""
    t0 = time.perf_counter()
    out = SklearnDBSCAN().run(
        DBSCANInput(gene_symbols=gene_symbols, epsilon=epsilon, min_points=min_pts)
    )
    return out.clusters, (time.perf_counter() - t0) * 1000


def agreement_section():
    print("=== AGREEMENT (real graph) ===")
    graph_json = os.environ.get("GENEWEAVER_DBSCAN_GRAPH_JSON")
    if not graph_json:
        print("  (set GENEWEAVER_DBSCAN_GRAPH_JSON to a gene-symbols dump to run this)\n")
        return
    with open(graph_json) as fh:
        gene_symbols = json.load(fh)
    for eps, mp in [(1, 2), (1, 3), (2, 3), (2, 5)]:
        bc, _ = run_binary(gene_symbols, eps, mp)
        sc, _ = run_sklearn(gene_symbols, eps, mp)
        same = as_clusters(bc) == as_clusters(sc)
        # also report coverage overlap to characterise *how* they differ
        bg = {g for c in bc for g in c}
        sg = {g for c in sc for g in c}
        print(
            f"  eps={eps} minPts={mp}: binary {len(bc)} clusters / {len(bg)} genes, "
            f"sklearn {len(sc)} clusters / {len(sg)} genes  -> "
            f"{'IDENTICAL' if same else f'differ (clustered-gene Jaccard {len(bg & sg)}/{len(bg | sg)})'}"
        )
    print()


def speed_section():
    print("=== SPEED (synthetic, eps=2 minPts=3) ===")
    header = f"{'genes':>6} {'sets':>5} | {'binary(ms)':>11} | {'sklearn(ms)':>12} | {'speedup':>8} | agree"
    print(header)
    print("-" * len(header))
    sizes = [
        (100, 20, 20),
        (500, 100, 30),
        (1000, 200, 40),
        (2000, 400, 50),
        (5000, 1000, 60),
    ]
    for n_genes, n_sets, gps in sizes:
        gs = make_gene_symbols(n_genes, n_sets, gps)
        try:
            bc, bt = run_binary(gs, 2, 3)
        except (subprocess.CalledProcessError, OSError) as e:
            bc, bt = None, None
            note = f"binary failed: {str(e)[:40]}"
        sc, st = run_sklearn(gs, 2, 3)
        if bt is None:
            print(f"{n_genes:>6} {n_sets:>5} | {'--':>11} | {st:>12.1f} | {'--':>8} | {note}")
            continue
        speedup = bt / st if st else float("inf")
        agree = as_clusters(bc) == as_clusters(sc)
        print(
            f"{n_genes:>6} {n_sets:>5} | {bt:>11.1f} | {st:>12.1f} | "
            f"{speedup:>7.2f}x | {'yes' if agree else 'no'}"
        )


def main():
    agreement_section()
    speed_section()


if __name__ == "__main__":
    main()
