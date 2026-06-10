"""Validate the ported PhenomeMap tool against the legacy in-memory post-processing.

Both consume the SAME `biclique` binary output, so this isolates and validates the only
thing the port changed: the Python pipeline (subset links, scoring, p-value/FDR trim,
cut-depth, unconnected trim) -- plus the scipy KS swap (scores compared within tolerance).

Pulls a real bipartite gene/gene-set graph + gene ranks from the local DB.

Usage:
    GENEWEAVER_BICLIQUE_BINARY=/tmp/biclique_build/biclique \
    python scripts/validation/validate_phenomemap.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import psycopg

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "tools", "src"))

from _legacy_phenomemap import run_legacy
from geneweaver.tools.phenome_map import PhenomeMap, PhenomeMapInput
from geneweaver.tools.phenome_map.tool import build_edge_list, parse_bicliques

DSN = "host=127.0.0.1 port=5433 dbname=geneweaver-dev user=geneweaver-dev password=localdev"
# Two disjoint hub clusters (mouse + human) -> parallel nested hierarchies, so several
# bicliques share a gene-set count (a "level" with >1 node) -> the cut-depth path can fire.
GENESET_IDS = [
    32922,
    32912,
    32408,
    34487,
    34486,
    32556,
    34654,
    24782,
    34635,
    270367,
    270916,
    366327,
    367071,
    370199,
    370345,
    371538,
    371987,
]
BINARY = os.environ["GENEWEAVER_BICLIQUE_BINARY"]


def load_graph(cur):
    """gene_sets: 'GS<id>' -> [ode_gene_id...]; gene_ranks: ode_gene_id -> rank."""
    gene_sets: dict[str, list[str]] = {}
    all_genes: set[int] = set()
    for gs_id in GENESET_IDS:
        cur.execute(
            "SELECT ode_gene_id FROM extsrc.geneset_value "
            "WHERE gs_id = %s AND gsv_in_threshold ORDER BY ode_gene_id",
            (gs_id,),
        )
        members = [r[0] for r in cur.fetchall()]
        gene_sets[f"GS{gs_id}"] = [str(g) for g in members]
        all_genes.update(members)
    cur.execute(
        "SELECT ode_gene_id, gene_rank FROM extsrc.gene_info "
        "WHERE ode_gene_id = ANY(%s) AND gene_rank IS NOT NULL",
        (list(all_genes),),
    )
    gene_ranks = {str(g): float(r) for g, r in cur.fetchall()}
    return gene_sets, gene_ranks


def biclique_runner(edge_list_text: str) -> str:
    """Write the edge list to a temp file and run the (rebuilt) biclique binary."""
    workdir = tempfile.mkdtemp(prefix="pm_validate_")
    el = os.path.join(workdir, "g.el")
    with open(el, "w") as fh:
        fh.write(edge_list_text)
    res = subprocess.run([BINARY, el, "-p"], capture_output=True, text=True, check=True)
    return res.stdout


def port_structure(output):
    """Map the port's output to the same {nodes, links} keyed-by-frozenset structure."""
    by_id = {n.id: frozenset(n.genesets) for n in output.nodes}
    nodes = {frozenset(n.genesets): sorted(n.genes) for n in output.nodes}
    links = {}
    for n in output.nodes:
        for link in n.children:
            links[(frozenset(n.genesets), by_id[link.target])] = link.score
    return {"nodes": nodes, "links": links, "cut_depth": output.cut_depth}


def compare(label, legacy, port, *, tol=1e-9):
    """Compare legacy vs port {nodes, links, cut_depth}; print a line and return match bool."""
    ok = True
    if set(legacy["nodes"]) != set(port["nodes"]):
        ok = False
        only_l = set(legacy["nodes"]) - set(port["nodes"])
        only_p = set(port["nodes"]) - set(legacy["nodes"])
        print(f"  [{label}] NODE MISMATCH  legacy-only={len(only_l)} port-only={len(only_p)}")
    else:
        for fs, genes in legacy["nodes"].items():
            if genes != port["nodes"][fs]:
                ok = False
                print(f"  [{label}] gene set differ for node {sorted(fs)}")
    if set(legacy["links"]) != set(port["links"]):
        ok = False
        only_l = set(legacy["links"]) - set(port["links"])
        only_p = set(port["links"]) - set(legacy["links"])
        print(f"  [{label}] LINK MISMATCH  legacy-only={len(only_l)} port-only={len(only_p)}")
    else:
        max_diff = 0.0
        for k, s in legacy["links"].items():
            max_diff = max(max_diff, abs(s - port["links"][k]))
        if max_diff > tol:
            ok = False
            print(f"  [{label}] SCORE drift max={max_diff:.3e} > tol {tol:.0e}")
        else:
            print(
                f"  [{label}] nodes={len(legacy['nodes'])} links={len(legacy['links'])} "
                f"cut_depth={legacy['cut_depth']} max_score_diff={max_diff:.2e}  OK"
            )
    if legacy["cut_depth"] != port["cut_depth"]:
        ok = False
        print(
            f"  [{label}] cut_depth differ legacy={legacy['cut_depth']} port={port['cut_depth']}"
        )
    return ok


def main():
    """Build the graph from the DB, run both implementations, and compare all cases."""
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        gene_sets, gene_ranks = load_graph(cur)

    edge_list_text, n_genes, n_gs = build_edge_list(gene_sets)
    raw = biclique_runner(edge_list_text)
    parsed = parse_bicliques(raw)
    print(
        f"graph: {n_gs} gene sets, {n_genes} genes, {len(gene_ranks)} ranks; "
        f"{len(parsed)} bicliques enumerated by the C binary"
    )

    tool = PhenomeMap(biclique_runner=lambda _e: raw)
    cases = [
        (
            "default(no trim)",
            {"min_genes": 1, "max_level": 0, "p_value_threshold": 1.0, "use_fdr": False},
        ),
        ("pval=0.5", {"min_genes": 1, "max_level": 0, "p_value_threshold": 0.5, "use_fdr": False}),
        (
            "pval=0.5+FDR",
            {"min_genes": 1, "max_level": 0, "p_value_threshold": 0.5, "use_fdr": True},
        ),
        (
            "min_genes=20",
            {"min_genes": 20, "max_level": 0, "p_value_threshold": 1.0, "use_fdr": False},
        ),
        (
            "max_level=2",
            {"min_genes": 1, "max_level": 2, "p_value_threshold": 1.0, "use_fdr": False},
        ),
        (
            "max_level=1(cut)",
            {"min_genes": 1, "max_level": 1, "p_value_threshold": 1.0, "use_fdr": False},
        ),
    ]
    all_ok = True
    for label, params in cases:
        legacy = run_legacy(parsed, gene_ranks, **params)
        port = port_structure(tool.run(PhenomeMapInput(gene_sets=gene_sets, **params)))
        all_ok &= compare(label, legacy, port)

    print("\nRESULT:", "ALL CASES MATCH ✓" if all_ok else "MISMATCHES FOUND ✗")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
