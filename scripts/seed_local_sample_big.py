"""Local-dev only: pull a larger curated slice of dev DB into local Postgres.

Differences from seed_local_sample.py:
  - autocommit on dst (so rollbacks during stub-user insert don't kill prior COPY work)
  - SAMPLE_LIMIT via env, default 50000
  - chunked dependent-id discovery / IN-clauses to avoid pathological query plans
  - progress prints so 25-min run isn't silent
"""

from __future__ import annotations

import os
import sys
import time

import psycopg

SRC = dict(host="127.0.0.1", port=5432, user="geneweaver-dev", dbname="geneweaver-dev")
DST = dict(
    host="127.0.0.1",
    port=5433,
    user="geneweaver-dev",
    dbname="geneweaver-dev",
    password="localdev",
)

SAMPLE_LIMIT = int(os.environ.get("SAMPLE_LIMIT", "50000"))


def now() -> str:
    return time.strftime("%H:%M:%S")


def copy_table(src, dst, table: str, where: str = "") -> None:
    sql_src = f"COPY (SELECT * FROM {table} {where}) TO STDOUT (FORMAT BINARY)"
    sql_dst = f"COPY {table} FROM STDIN (FORMAT BINARY)"
    with src.cursor().copy(sql_src) as sc, dst.cursor().copy(sql_dst) as dc:
        for chunk in sc:
            dc.write(chunk)


def in_clause(ids, col: str) -> str:
    if not ids:
        return "WHERE FALSE"
    return f"WHERE {col} IN ({','.join(str(int(i)) for i in ids)})"


def main() -> None:
    src_pw = os.environ["SRC_DB_PASSWORD"]
    src = psycopg.connect(**SRC, password=src_pw)
    dst = psycopg.connect(**DST, autocommit=True)

    with dst.cursor() as c:
        c.execute("SET session_replication_role = replica")
        # Clear previous sample so PKs don't collide on the new draw
        c.execute(
            "TRUNCATE extsrc.geneset_value, extsrc.gene_info, extsrc.gene, "
            "production.geneset_info, production.geneset, production.publication, "
            "production.file, production.usr RESTART IDENTITY CASCADE"
        )
        print(f"[{now()}] cleared previous sample")

    print(f"[{now()}] Picking {SAMPLE_LIMIT} genesets (status=normal, gs_count 5-200)")
    with src.cursor() as c:
        c.execute(
            """
            SELECT gs_id FROM production.geneset
            WHERE gs_status = 'normal'
              AND gs_count BETWEEN 5 AND 200
              AND cur_id IS NOT NULL
            ORDER BY random()
            LIMIT %s
            """,
            (SAMPLE_LIMIT,),
        )
        gs_ids = [r[0] for r in c.fetchall()]
    print(f"[{now()}]   got {len(gs_ids)} gs_ids")

    # Use a temp table on src to make the dependent queries fast
    print(f"[{now()}] Building temp table on src for fast joins")
    with src.cursor() as c:
        c.execute("CREATE TEMP TABLE sample_gs (gs_id bigint PRIMARY KEY) ON COMMIT PRESERVE ROWS")
        with c.copy("COPY sample_gs (gs_id) FROM STDIN") as cp:
            for gid in gs_ids:
                cp.write_row([gid])
        c.execute("ANALYZE sample_gs")

    print(f"[{now()}] Discovering deps via joins")
    with src.cursor() as c:
        c.execute(
            "SELECT DISTINCT g.usr_id FROM production.geneset g JOIN sample_gs s USING (gs_id) WHERE g.usr_id IS NOT NULL"
        )
        usr_ids = [r[0] for r in c.fetchall()]
        c.execute(
            "SELECT DISTINCT g.pub_id FROM production.geneset g JOIN sample_gs s USING (gs_id) WHERE g.pub_id IS NOT NULL"
        )
        pub_ids = [r[0] for r in c.fetchall()]
        c.execute(
            "SELECT DISTINCT g.file_id FROM production.geneset g JOIN sample_gs s USING (gs_id) WHERE g.file_id IS NOT NULL"
        )
        file_ids = [r[0] for r in c.fetchall()]
        c.execute(
            "SELECT DISTINCT v.ode_gene_id FROM extsrc.geneset_value v JOIN sample_gs s USING (gs_id)"
        )
        ode_gene_ids = [r[0] for r in c.fetchall()]
    print(
        f"[{now()}]   deps: {len(usr_ids)} usrs, {len(pub_ids)} pubs, {len(file_ids)} files, {len(ode_gene_ids)} ode_gene_ids"
    )

    # Stub anonymized user rows (avoids PII)
    print(f"[{now()}] Inserting stub users")
    with dst.cursor() as c:
        for batch_start in range(0, len(usr_ids), 5000):
            batch = usr_ids[batch_start : batch_start + 5000]
            args = []
            for uid in batch:
                args.extend([uid, f"stub-{uid}@local.invalid", "Stub", f"User-{uid}", 0, False, "{}"])
            placeholders = ",".join(["(%s,%s,%s,%s,%s,%s,%s)"] * len(batch))
            c.execute(
                f"INSERT INTO production.usr (usr_id, usr_email, usr_first_name, usr_last_name, usr_admin, is_guest, usr_prefs) VALUES {placeholders} ON CONFLICT DO NOTHING",
                args,
            )

    # JOIN-based COPY directly from src using the temp table — avoids huge IN clauses
    print(f"[{now()}] Copying dependent rows")
    plan = [
        ("production.file", f"WHERE file_id IN ({','.join(str(int(i)) for i in file_ids)})" if file_ids else "WHERE FALSE"),
        ("production.publication", f"WHERE pub_id IN ({','.join(str(int(i)) for i in pub_ids)})" if pub_ids else "WHERE FALSE"),
        # Use temp-table join via sample_gs - need to embed in COPY (SELECT ... )
        ("production.geneset", "JOIN", "SELECT g.* FROM production.geneset g JOIN sample_gs s USING (gs_id)"),
        ("production.geneset_info", "JOIN", "SELECT i.* FROM production.geneset_info i JOIN sample_gs s USING (gs_id)"),
        ("extsrc.geneset_value", "JOIN", "SELECT v.* FROM extsrc.geneset_value v JOIN sample_gs s USING (gs_id)"),
    ]
    for entry in plan:
        if entry[1] == "JOIN":
            tbl, _, select_sql = entry
            t0 = time.time()
            sql_src = f"COPY ({select_sql}) TO STDOUT (FORMAT BINARY)"
            sql_dst = f"COPY {tbl} FROM STDIN (FORMAT BINARY)"
            with src.cursor().copy(sql_src) as sc, dst.cursor().copy(sql_dst) as dc:
                for chunk in sc:
                    dc.write(chunk)
            with dst.cursor() as c:
                c.execute(f"SELECT count(*) FROM {tbl}")
                n = c.fetchone()[0]
            print(f"[{now()}]   {tbl}: {n} rows ({time.time()-t0:.1f}s)")
        else:
            tbl, where = entry
            t0 = time.time()
            try:
                copy_table(src, dst, tbl, where=where)
                with dst.cursor() as c:
                    c.execute(f"SELECT count(*) FROM {tbl}")
                    n = c.fetchone()[0]
                print(f"[{now()}]   {tbl}: {n} rows ({time.time()-t0:.1f}s)")
            except Exception as e:
                print(f"[{now()}]   {tbl}: SKIPPED ({e})")

    # Genes: chunked since ode_gene_ids can be large
    print(f"[{now()}] Copying genes ({len(ode_gene_ids)} ode_gene_ids)")
    for tbl in ["extsrc.gene", "extsrc.gene_info"]:
        t0 = time.time()
        # Use a temp table approach for genes too
        with src.cursor() as c:
            c.execute("DROP TABLE IF EXISTS sample_genes")
            c.execute("CREATE TEMP TABLE sample_genes (ode_gene_id bigint PRIMARY KEY) ON COMMIT PRESERVE ROWS")
            with c.copy("COPY sample_genes (ode_gene_id) FROM STDIN") as cp:
                for gid in ode_gene_ids:
                    cp.write_row([gid])
            c.execute("ANALYZE sample_genes")
        sql_src = f"COPY (SELECT t.* FROM {tbl} t JOIN sample_genes s USING (ode_gene_id)) TO STDOUT (FORMAT BINARY)"
        sql_dst = f"COPY {tbl} FROM STDIN (FORMAT BINARY)"
        with src.cursor().copy(sql_src) as sc, dst.cursor().copy(sql_dst) as dc:
            for chunk in sc:
                dc.write(chunk)
        with dst.cursor() as c:
            c.execute(f"SELECT count(*) FROM {tbl}")
            n = c.fetchone()[0]
        print(f"[{now()}]   {tbl}: {n} rows ({time.time()-t0:.1f}s)")
        # only build sample_genes once - drop after first use is fine, but src conn persists
        break  # gene_info uses different keys per ode_gene_id, do separately
    # gene_info
    t0 = time.time()
    sql_src = f"COPY (SELECT t.* FROM extsrc.gene_info t JOIN sample_genes s USING (ode_gene_id)) TO STDOUT (FORMAT BINARY)"
    sql_dst = f"COPY extsrc.gene_info FROM STDIN (FORMAT BINARY)"
    with src.cursor().copy(sql_src) as sc, dst.cursor().copy(sql_dst) as dc:
        for chunk in sc:
            dc.write(chunk)
    with dst.cursor() as c:
        c.execute(f"SELECT count(*) FROM extsrc.gene_info")
        n = c.fetchone()[0]
    print(f"[{now()}]   extsrc.gene_info: {n} rows ({time.time()-t0:.1f}s)")

    with dst.cursor() as c:
        c.execute("SET session_replication_role = origin")

    # Reset sequences past max IDs so the legacy app can insert new guest users etc.
    print(f"[{now()}] Resetting sequences")
    with dst.cursor() as c:
        for tbl, col in [
            ("production.usr", "usr_id"),
            ("production.geneset", "gs_id"),
            ("production.publication", "pub_id"),
            ("production.file", "file_id"),
        ]:
            c.execute(
                f"SELECT setval(pg_get_serial_sequence('{tbl}','{col}'), GREATEST(COALESCE(MAX({col}),0), 1) + 1) FROM {tbl}"
            )

    print(f"[{now()}] DONE")


if __name__ == "__main__":
    sys.exit(main())
