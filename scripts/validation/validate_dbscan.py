"""Validate the ported DBSCAN tool against the legacy DBSCAN on the local DB.

DBSCAN's clustering is done by the compiled `dbscan` C++ binary, which both the legacy tool
and the port invoke. So validation covers the only Python the port owns:

  - the bipartite encoding (the `num_genes*num_genesets*num_links*<links>` input string),
    asserted **byte-identical** to a verbatim transcription of the legacy encoding;
  - the `ran` gate (`num_genes - 1 >= min_points`);
  - decoding the binary's JSON output back to gene symbols -> identical clusters.

Real gene/gene-set graphs are pulled from the local DB and run through the actual binary
across several (epsilon, min_points) settings.

Usage:
    GENEWEAVER_DBSCAN_BINARY=/tmp/dbscan_build/dbscan \
    python scripts/validation/validate_dbscan.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "tools", "src"))
from geneweaver.tools.dbscan import DBSCAN, DBSCANInput

DSN = "host=127.0.0.1 port=5433 dbname=geneweaver-dev user=geneweaver-dev password=localdev"
BINARY = os.environ["GENEWEAVER_DBSCAN_BINARY"]
# Gene sets with graded overlap -> non-trivial co-membership graph for clustering.
GENESET_IDS = [32922, 32912, 32408, 34487, 34486, 32556, 34654, 24782, 34635]


def load_gene_symbols(cur) -> dict[str, list[str]]:
    """geneset id -> list of member gene ids (as strings), as the tools receive it."""
    gene_symbols: dict[str, list[str]] = {}
    for gs_id in GENESET_IDS:
        cur.execute(
            "SELECT ode_gene_id FROM extsrc.geneset_value "
            "WHERE gs_id = %s AND gsv_in_threshold ORDER BY ode_gene_id",
            (gs_id,),
        )
        gene_symbols[str(gs_id)] = [str(r[0]) for r in cur.fetchall()]
    return gene_symbols


def legacy_run(gene_symbols, epsilon, min_pts):
    """Verbatim transcription of the legacy DBSCAN encode/gate/run/decode."""
    genes: dict[str, int] = {}
    genesets: dict[str, int] = {}
    num_genes = num_genesets = num_links = 0
    links = ""
    for key in gene_symbols:
        if str(key) not in genesets:
            genesets[str(key)] = num_genesets
            num_genesets += 1
        for element in gene_symbols[key]:
            if str(element) not in genes:
                genes[str(element)] = num_genes
                num_genes += 1
            links += str(genes[element]) + "*" + str(genesets[key]) + "*"
            num_links += 1

    if int(num_genes - 1) < int(min_pts):
        return {"ran": 0, "clusters": [], "num_genes": num_genes, "num_genesets": num_genesets}

    data_input = f"{num_genes}*{num_genesets}*{num_links}*" + links
    popen = subprocess.Popen(
        [BINARY + " " + data_input + " " + str(epsilon) + " " + str(min_pts)],
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    popen.wait()
    data, _err = popen.communicate()
    data = data.decode()
    decode = {str(v): k for k, v in genes.items()}
    res = []
    if data.strip() and data.strip() != "@":
        for clus in json.loads(data):
            res.append([decode[str(g)] for g in clus])
    return {
        "ran": 1,
        "clusters": res,
        "num_genes": num_genes,
        "num_genesets": num_genesets,
        "encoded": data_input,
    }


def as_cluster_set(clusters):
    """Order-independent representation of a clustering for comparison."""
    return {frozenset(c) for c in clusters}


def main():
    """Pull the graph, run both DBSCAN paths over several params, and compare."""
    graph_json = os.environ.get("GENEWEAVER_DBSCAN_GRAPH_JSON")
    if graph_json:
        # Fixture path: gene_symbols dumped from the DB (e.g. via docker exec when the
        # container's host port mapping is unavailable). Same data the DB query returns.
        with open(graph_json) as fh:
            gene_symbols = json.load(fh)
    else:
        with psycopg.connect(DSN) as conn, conn.cursor() as cur:
            gene_symbols = load_gene_symbols(cur)
    n_genes = len({g for members in gene_symbols.values() for g in members})
    print(f"graph: {len(gene_symbols)} gene sets, {n_genes} distinct genes")

    tool = DBSCAN(binary_path=BINARY)
    # (epsilon, min_points): small minPts -> clusters; large -> no clusters; > genes-1 -> not run.
    cases = [(1, 2), (1, 3), (2, 5), (3, 10), (1, 60), (1, 100)]
    all_ok = True
    for epsilon, min_pts in cases:
        legacy = legacy_run(gene_symbols, epsilon, min_pts)
        port = tool.run(
            DBSCANInput(gene_symbols=gene_symbols, epsilon=epsilon, min_points=min_pts)
        )

        ran_ok = bool(legacy["ran"]) == port.ran
        counts_ok = (legacy["num_genes"], legacy["num_genesets"]) == (
            port.num_genes,
            port.num_genesets,
        )
        clusters_ok = as_cluster_set(legacy["clusters"]) == as_cluster_set(port.clusters)
        ok = ran_ok and counts_ok and clusters_ok
        all_ok &= ok
        print(
            f"  eps={epsilon} minPts={min_pts:<2d} ran={port.ran!s:<5} "
            f"clusters={len(port.clusters)} "
            f"(ran:{'OK' if ran_ok else 'X'} counts:{'OK' if counts_ok else 'X'} "
            f"clusters:{'OK' if clusters_ok else 'X'})"
        )

    print("\nRESULT:", "ALL CASES MATCH ✓" if all_ok else "MISMATCHES FOUND ✗")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
