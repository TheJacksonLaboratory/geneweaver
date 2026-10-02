"""Fetch the OLD-rule universe membership (Tier I-III curated genes) for mouse and human."""

import json
import os
import pathlib
import time

import psycopg

OUT = pathlib.Path(os.environ.get("MSET_IMPACT_DIR", "/tmp/mset-impact"))
conn = psycopg.connect(
    f"host=127.0.0.1 port=5434 dbname={os.environ['DB_NAME']} user={os.environ['DB_USERNAME']} password={os.environ['DB_PASSWORD']}",
    connect_timeout=15,
)
conn.read_only = True
# Mirrors createBackgrounds.py exactly: gi_symbol of genes with a gdb_id=7 entry that
# appear in any gene set of this species whose cur_id is set and not 4 or 5.
OLD = """
SELECT DISTINCT gi.gi_symbol
FROM production.geneset gs
JOIN extsrc.geneset_value gv ON gv.gs_id = gs.gs_id
JOIN extsrc.gene g ON g.ode_gene_id = gv.ode_gene_id AND g.gdb_id = 7
JOIN extsrc.gene_info gi ON gi.ode_gene_id = gv.ode_gene_id
WHERE gs.cur_id IS NOT NULL AND gs.cur_id NOT IN (4,5) AND gs.sp_id = %(sp)s
"""
NEW = """SELECT DISTINCT ode_ref_id FROM extsrc.gene
         WHERE sp_id=%(sp)s AND gdb_id=7 AND ode_pref='t'"""
with conn, conn.cursor() as cur:
    cur.execute("SET statement_timeout='1500s'")
    for sp in (1, 2):
        t = time.time()
        cur.execute(OLD, {"sp": sp})
        old = sorted({r[0] for r in cur.fetchall() if r[0]})
        cur.execute(NEW, {"sp": sp})
        new = sorted({r[0] for r in cur.fetchall() if r[0]})
        print(
            f"sp={sp}: old={len(old):,} new={len(new):,} ratio={len(new) / len(old):.3f} ({time.time() - t:.0f}s)",
            flush=True,
        )
        (OUT / f"old_universe_{sp}.json").write_text(json.dumps(old))
        (OUT / f"new_universe_{sp}.json").write_text(json.dumps(new))
print("saved")
