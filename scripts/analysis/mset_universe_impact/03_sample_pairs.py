"""Sample real curated gene-set pairs from dev and record K, n, k for each."""

import json
import os
import pathlib
import random

import psycopg

random.seed(11)
OUT = pathlib.Path(os.environ.get("MSET_IMPACT_DIR", "/tmp/mset-impact"))
conn = psycopg.connect(
    f"host=127.0.0.1 port=5434 dbname={os.environ['DB_NAME']} user={os.environ['DB_USERNAME']} password={os.environ['DB_PASSWORD']}",
    connect_timeout=15,
)
conn.read_only = True
SPECIES = {1: "Mus musculus", 2: "Homo sapiens"}
result = {}
with conn, conn.cursor() as cur:
    cur.execute("SET statement_timeout='900s'")
    for sp in SPECIES:
        # Realistic MSET inputs: curated (Tier I-III), normal status, sensible size.
        cur.execute(
            """
            SELECT gs_id FROM production.geneset
            WHERE sp_id=%(sp)s AND cur_id IS NOT NULL AND cur_id NOT IN (4,5)
              AND gs_status='normal' AND gs_count BETWEEN 10 AND 1000
            ORDER BY random() LIMIT 400
        """,
            {"sp": sp},
        )
        ids = [r[0] for r in cur.fetchall()]
        # One fetch for every member list, in the same space the tools use.
        cur.execute(
            """
            SELECT gv.gs_id, g.ode_ref_id
            FROM extsrc.geneset_value gv
            JOIN extsrc.gene g ON g.ode_gene_id = gv.ode_gene_id
            WHERE gv.gs_id = ANY(%(ids)s) AND g.gdb_id=7 AND g.ode_pref='t'
        """,
            {"ids": ids},
        )
        members = {}
        for gs_id, sym in cur.fetchall():
            members.setdefault(gs_id, set()).add(sym)
        members = {k: v for k, v in members.items() if len(v) >= 10}
        keys = sorted(members)
        random.shuffle(keys)
        pairs = []
        for a, b in zip(keys[0::2], keys[1::2], strict=False):
            pairs.append(
                {
                    "a": a,
                    "b": b,
                    "K": len(members[a]),
                    "n": len(members[b]),
                    "k": len(members[a] & members[b]),
                }
            )
        result[sp] = pairs
        print(f"sp={sp} {SPECIES[sp]}: {len(members)} sets -> {len(pairs)} pairs", flush=True)
        (OUT / f"members_{sp}.json").write_text(
            json.dumps({str(k): sorted(v) for k, v in members.items()})
        )
(OUT / "pairs.json").write_text(json.dumps(result))
print("saved")
