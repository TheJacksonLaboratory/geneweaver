import json
import os
import pathlib
import time

import psycopg

conn = psycopg.connect(
    f"host=127.0.0.1 port=5434 dbname={os.environ['DB_NAME']} user={os.environ['DB_USERNAME']} password={os.environ['DB_PASSWORD']}",
    connect_timeout=15,
)
conn.read_only = True
with conn, conn.cursor() as cur:
    cur.execute("SET statement_timeout = '1500s'")
    cur.execute("SELECT sp_id, sp_name FROM odestatic.species WHERE sp_id<>0")
    names = dict(cur.fetchall())
    t = time.time()
    # One grouped pass: symbols of genes appearing in any Tier I-III gene set, per species.
    cur.execute("""
        SELECT gs.sp_id, count(DISTINCT gi.gi_symbol)
        FROM production.geneset gs
        JOIN extsrc.geneset_value gv ON gv.gs_id = gs.gs_id
        JOIN extsrc.gene g ON g.ode_gene_id = gv.ode_gene_id AND g.gdb_id = 7
        JOIN extsrc.gene_info gi ON gi.ode_gene_id = gv.ode_gene_id
        WHERE gs.cur_id IS NOT NULL AND gs.cur_id NOT IN (4, 5)
        GROUP BY gs.sp_id
    """)
    old = dict(cur.fetchall())
    print(f"old-rule pass: {time.time() - t:.0f}s", flush=True)
    cur.execute("""SELECT sp_id, count(DISTINCT ode_ref_id) FROM extsrc.gene
                   WHERE gdb_id=7 AND ode_pref='t' AND sp_id<>0 GROUP BY sp_id""")
    new = dict(cur.fetchall())

print(f"\n{'sp':>3} {'species':<26}{'OLD Tier I-III':>16}{'NEW all':>11}{'ratio':>10}")
rows = []
for sp in sorted(set(old) | set(new)):
    o, n = old.get(sp, 0), new.get(sp, 0)
    r = (n / o) if o else None
    rows.append({"sp_id": sp, "name": names.get(sp, "?"), "old": o, "new": n, "ratio": r})
    print(f"{sp:>3} {names.get(sp, '?'):<26}{o:>16,}{n:>11,}{(f'{r:.2f}x' if r else 'was 0'):>10}")
pathlib.Path("/tmp/mset-impact/universes.json").write_text(json.dumps(rows))
