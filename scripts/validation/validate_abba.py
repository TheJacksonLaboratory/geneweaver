"""Validate the ported ABBA db-layer function against the legacy ABBA SQL on the local DB.

Runs the ported `geneweaver.db.abba.abba()` and a faithful transcription of the legacy
ABBA SQL pipeline (legacy/tools-worker/tools/ABBA.py, homology-on path) against the same
database, then compares genes-of-interest, matching gene sets, result genes, and the
available-counts. (The local `extsrc.homology` table is empty, so homology expansion is a
no-op here -- genes of interest == input genes -- but the matching/result aggregation, the
group-access gate, the auto min-genes gate, and the tier/species filters are all exercised.)

Usage:
    python scripts/validation/validate_abba.py
"""

from __future__ import annotations

import os
import sys

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "db", "src"))
from geneweaver.db.abba import abba

DSN = "host=127.0.0.1 port=5433 dbname=geneweaver-dev user=geneweaver-dev password=localdev"
SEED_GENESET = 514  # take this gene set's symbols as the ABBA input genes
SPECIES = [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11]
TIERS = [1, 2, 3, 4, 5]
USER_ID = 0


def input_symbols(cur) -> list[str]:
    """Lower-cased preferred gene symbols belonging to the seed gene set."""
    cur.execute(
        "SELECT DISTINCT lower(g.ode_ref_id) FROM extsrc.geneset_value gv "
        "JOIN extsrc.gene g ON g.ode_gene_id = gv.ode_gene_id "
        "WHERE gv.gs_id = %s AND gv.gsv_in_threshold AND g.gdb_id = 7 AND g.ode_pref",
        (SEED_GENESET,),
    )
    return [r[0] for r in cur.fetchall()]


def run_legacy(cur, genes: list[str]) -> dict:
    """Faithful transcription of the legacy ABBA SQL (homology-on path)."""
    sp = "IN (" + ",".join(str(x) for x in SPECIES) + ")"
    tiers = "IN (" + ",".join(str(x) for x in TIERS) + ")"
    in_genes = "IN ('" + "','".join(g.replace("'", "''") for g in genes) + "')"

    for t in ("abba_in_l", "abba_interest_l", "abba_matching_l", "abba_result_l"):
        cur.execute(f"DROP TABLE IF EXISTS {t}")

    cur.execute(
        f"CREATE TEMP TABLE abba_in_l AS SELECT * FROM extsrc.gene "
        f"WHERE lower(ode_ref_id) {in_genes} AND sp_id {sp} AND gdb_id=7"
    )
    # homology-on branch (verbatim structure)
    cur.execute(
        f"CREATE TEMP TABLE abba_interest_l AS "
        f"(SELECT * FROM extsrc.gene WHERE ode_gene_id IN "
        f"(SELECT ode_gene_id FROM extsrc.homology WHERE hom_id IN "
        f"(SELECT hom_id FROM extsrc.homology h JOIN abba_in_l ig ON h.ode_gene_id=ig.ode_gene_id)) "
        f"AND gdb_id=7 AND ode_pref=true AND sp_id {sp}) "
        f"UNION DISTINCT (SELECT * FROM abba_in_l)"
    )
    cur.execute(
        "CREATE TEMP TABLE abba_matching_l AS "
        "SELECT count(ode_gene_id) AS genematchcount, gs.* "
        "FROM extsrc.geneset_value gv JOIN production.geneset gs ON gv.gs_id=gs.gs_id "
        "WHERE ode_gene_id IN (SELECT ode_gene_id FROM abba_interest_l) "
        "AND gs_status='normal' AND gv.gsv_in_threshold "
        "AND (ARRAY(SELECT grp_id FROM production.usr2grp WHERE usr_id=0)||0 "
        "@> string_to_array(gs_groups, ',')::int[]) GROUP BY gs.gs_id"
    )
    cur.execute(
        f"CREATE TEMP TABLE abba_result_l AS "
        f"SELECT gi.*, count(gv.ode_gene_id) AS occurrences "
        f"FROM extsrc.geneset_value gv JOIN extsrc.gene_info gi ON gv.ode_gene_id=gi.ode_gene_id "
        f"WHERE gv.gsv_in_threshold AND gv.gs_id IN "
        f"(SELECT gs_id FROM abba_matching_l "
        f"WHERE genematchcount >= least((SELECT count(DISTINCT ode_ref_id) FROM abba_interest_l),1) "
        f"AND cur_id {tiers} AND sp_id {sp}) "
        f"GROUP BY gi.ode_gene_id HAVING lower(gi.gi_symbol) NOT IN "
        f"(SELECT DISTINCT lower(ode_ref_id) FROM abba_interest_l)"
    )

    cur.execute("SELECT count(*) FROM extsrc.gene WHERE gdb_id=7 AND ode_pref=TRUE")
    available_genes = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM production.geneset WHERE cur_id {tiers}")
    available_genesets = cur.fetchone()[0]
    cur.execute(
        "SELECT DISTINCT ON (a.ode_gene_id) a.ode_gene_id FROM abba_interest_l a, "
        "odestatic.species b WHERE a.sp_id=b.sp_id ORDER BY a.ode_gene_id"
    )
    goi = {r[0] for r in cur.fetchall()}
    cur.execute(
        f"SELECT gs_id, genematchcount FROM abba_matching_l "
        f"WHERE genematchcount >= -1 AND cur_id {tiers} "
        f"ORDER BY genematchcount DESC, gs_count LIMIT 50"
    )
    matching = {(r[0], r[1]) for r in cur.fetchall()}
    cur.execute(
        "SELECT * FROM (SELECT DISTINCT ON (a.ode_gene_id) a.ode_gene_id, a.occurrences "
        "FROM abba_result_l a, extsrc.gene b, odestatic.species c "
        "WHERE a.ode_gene_id=b.ode_gene_id AND b.sp_id=c.sp_id AND a.occurrences >= -1) r "
        "ORDER BY occurrences DESC LIMIT 50"
    )
    result_genes = {(r[0], r[1]) for r in cur.fetchall()}
    return {
        "available_genes": available_genes,
        "available_genesets": available_genesets,
        "goi": goi,
        "matching": matching,
        "result_genes": result_genes,
    }


def main():
    """Run the ported abba() and the legacy SQL on the same DB and compare the results."""
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            genes = input_symbols(cur)
        print(f"input genes: {len(genes)} symbols from gene set {SEED_GENESET}")

        # ported tool
        with conn.cursor() as cur:
            port = abba(
                cur,
                genes,
                species_ids=SPECIES,
                tiers=TIERS,
                user_id=USER_ID,
                include_homology=True,
            )
        port_goi = {row[0] for row in port.genes_of_interest}
        port_matching = {(row[0], row[2]) for row in port.geneset_results}
        port_result = {(row[0], row[4]) for row in port.gene_results}

        # legacy reference
        with conn.cursor() as cur:
            legacy = run_legacy(cur, genes)
        conn.rollback()

    checks = [
        ("available_genes", port.available_genes, legacy["available_genes"]),
        ("available_genesets", port.available_genesets, legacy["available_genesets"]),
        ("genes_of_interest", port_goi, legacy["goi"]),
        ("matching_genesets(top50)", port_matching, legacy["matching"]),
        ("result_genes(top50)", port_result, legacy["result_genes"]),
    ]
    ok = True
    for name, p, exp in checks:
        match = p == exp
        ok &= match
        if isinstance(p, set):
            print(
                f"  {name:28s} port={len(p):<5d} legacy={len(exp):<5d} "
                f"{'OK' if match else f'MISMATCH (sym diff {len(p ^ exp)})'}"
            )
        else:
            print(f"  {name:28s} port={p:<7d} legacy={exp:<7d} {'OK' if match else 'MISMATCH'}")
    print("\nRESULT:", "ALL CHECKS MATCH ✓" if ok else "MISMATCHES FOUND ✗")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
