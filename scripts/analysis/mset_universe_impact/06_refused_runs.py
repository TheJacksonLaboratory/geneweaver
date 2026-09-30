"""How many gene sets cannot run MSET at all under the old rule?

The old background was built from Tier I-III sets, so their own genes are in it by
construction -- which is why a Tier I-III sample shows no refusals. The refusals land on
Tier IV/V sets (G3-783), which is what this measures.
"""

import json
import os
import pathlib

import psycopg

OUT = pathlib.Path(os.environ.get("MSET_IMPACT_DIR", "/tmp/mset-impact"))
conn = psycopg.connect(
    f"host=127.0.0.1 port=5434 dbname={os.environ['DB_NAME']} user={os.environ['DB_USERNAME']} password={os.environ['DB_PASSWORD']}",
    connect_timeout=15,
)
conn.read_only = True
with conn, conn.cursor() as cur:
    cur.execute("SET statement_timeout='1500s'")
    for sp in (1, 2):
        old_u = set(json.loads((OUT / f"old_universe_{sp}.json").read_text()))
        # Population of sets MSET could be asked to run but the old background excludes.
        cur.execute(
            """
            SELECT gs.gs_id, gs.cur_id, array_agg(g.ode_ref_id)
            FROM production.geneset gs
            JOIN extsrc.geneset_value gv ON gv.gs_id = gs.gs_id
            JOIN extsrc.gene g ON g.ode_gene_id = gv.ode_gene_id AND g.gdb_id=7 AND g.ode_pref='t'
            WHERE gs.sp_id=%(sp)s AND gs.gs_status='normal'
              AND gs.gs_count BETWEEN 10 AND 1000
              AND (gs.cur_id IS NULL OR gs.cur_id IN (4,5))
            GROUP BY gs.gs_id, gs.cur_id
            LIMIT 3000
        """,
            {"sp": sp},
        )
        rows = cur.fetchall()
        refused = 0
        out_fracs = []
        for _gs_id, _cur_id, syms in rows:
            members = {s for s in syms if s}
            if not members:
                continue
            outside = members - old_u
            if outside:
                refused += 1
                out_fracs.append(len(outside) / len(members))
        total = len(rows)
        print(f"sp={sp}: Tier IV/V-or-unassigned sets sampled {total}")
        if total:
            print(f"   would be REFUSED by the old background: {refused} ({refused / total:.0%})")
            if out_fracs:
                out_fracs.sort()
                med = out_fracs[len(out_fracs) // 2]
                print(
                    f"   of those, fraction of genes outside: median {med:.1%}, "
                    f"max {max(out_fracs):.1%}"
                )
        print(flush=True)
