"""Local-dev only: copy a curated slice of dev DB rows into the local Postgres.

Source: cloud-sql-proxy at 127.0.0.1:5432 (live dev DB)
Target: local docker container at 127.0.0.1:5433

Strategy:
  - small reference tables: full copy
  - production.geneset: sample N rows (status=normal, modest gs_count)
  - for the sampled gs_ids: pull dependent rows from geneset_value/gene/publication/file
  - skip production.usr (PII) — substitute a single stub user
"""

from __future__ import annotations

import os
import sys

import psycopg

SRC = dict(host="127.0.0.1", port=5432, user="geneweaver-dev", dbname="geneweaver-dev")
DST = dict(
    host="127.0.0.1",
    port=5433,
    user="geneweaver-dev",
    dbname="geneweaver-dev",
    password="localdev",
)

SAMPLE_LIMIT = int(os.environ.get("SAMPLE_LIMIT", "100"))

FULL_TABLES = [
    "odestatic.species",
    "odestatic.genedb",
    "odestatic.attribution",
    "odestatic.curation_levels",
    "odestatic.platform",
    "odestatic.ontologydb",
    "odestatic.tool",
    "odestatic.tool_param",
    "odestatic.special_terms",
    "production.grp",
    "gwcuration.status_types",
]


def copy_table(src, dst, table: str, where: str = "") -> int:
    """Stream COPY from src to dst. Returns rows transferred."""
    sql_src = f"COPY (SELECT * FROM {table} {where}) TO STDOUT (FORMAT BINARY)"
    sql_dst = f"COPY {table} FROM STDIN (FORMAT BINARY)"
    n = 0
    with src.cursor().copy(sql_src) as src_copy, dst.cursor().copy(sql_dst) as dst_copy:
        for chunk in src_copy:
            dst_copy.write(chunk)
            n += len(chunk)
    return n


def main() -> None:
    src_pw = os.environ["SRC_DB_PASSWORD"]
    with (
        psycopg.connect(**SRC, password=src_pw) as src,
        psycopg.connect(**DST) as dst,
    ):
        dst.execute("SET session_replication_role = replica")  # turn off FK checks

        print(f"[1/5] Full copy of {len(FULL_TABLES)} reference tables")
        for t in FULL_TABLES:
            try:
                copy_table(src, dst, t)
                with dst.cursor() as c:
                    c.execute(f"SELECT count(*) FROM {t}")
                    print(f"    {t}: {c.fetchone()[0]} rows")
            except Exception as e:
                print(f"    {t}: SKIPPED ({type(e).__name__}: {e})")
                dst.rollback()
                dst.execute("SET session_replication_role = replica")

        print(f"\n[2/5] Sample {SAMPLE_LIMIT} genesets")
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
        print(f"    picked {len(gs_ids)} gs_ids")

        # discover the dependencies the sample needs
        with src.cursor() as c:
            c.execute(
                "SELECT DISTINCT usr_id FROM production.geneset WHERE gs_id = ANY(%s) AND usr_id IS NOT NULL",
                (gs_ids,),
            )
            usr_ids = [r[0] for r in c.fetchall()]
            c.execute(
                "SELECT DISTINCT pub_id FROM production.geneset WHERE gs_id = ANY(%s) AND pub_id IS NOT NULL",
                (gs_ids,),
            )
            pub_ids = [r[0] for r in c.fetchall()]
            c.execute(
                "SELECT DISTINCT file_id FROM production.geneset WHERE gs_id = ANY(%s) AND file_id IS NOT NULL",
                (gs_ids,),
            )
            file_ids = [r[0] for r in c.fetchall()]
            c.execute(
                "SELECT DISTINCT ode_gene_id FROM extsrc.geneset_value WHERE gs_id = ANY(%s)",
                (gs_ids,),
            )
            ode_gene_ids = [r[0] for r in c.fetchall()]
        print(
            f"    deps: {len(usr_ids)} users, {len(pub_ids)} pubs, {len(file_ids)} files, {len(ode_gene_ids)} genes"
        )

        # stub user row (anonymized) for each usr_id referenced — avoids pulling real user PII
        print("\n[3/5] Stub anonymous user rows")
        with src.cursor() as src_c, dst.cursor() as dst_c:
            src_c.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='production' AND table_name='usr' ORDER BY ordinal_position"
            )
            usr_cols = [r[0] for r in src_c.fetchall()]
        # build INSERT with placeholders, using NULLs except usr_id and a stub email
        col_list = ", ".join(f'"{c}"' for c in usr_cols)
        placeholders = ", ".join(["%s"] * len(usr_cols))
        with dst.cursor() as dst_c:
            for uid in usr_ids:
                row = []
                for c in usr_cols:
                    if c == "usr_id":
                        row.append(uid)
                    elif c == "usr_email":
                        row.append(f"stub-{uid}@local.invalid")
                    elif c == "usr_first_name":
                        row.append("Stub")
                    elif c == "usr_last_name":
                        row.append(f"User-{uid}")
                    elif c == "usr_admin":
                        row.append(0)
                    else:
                        row.append(None)
                try:
                    dst_c.execute(
                        f"INSERT INTO production.usr ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                        row,
                    )
                except Exception as e:
                    print(f"    skip usr_id={uid}: {e}")
                    dst.rollback()
                    dst.execute("SET session_replication_role = replica")
            dst.commit()
        print(f"    inserted up to {len(usr_ids)} stub users")

        # dependent rows
        print("\n[4/5] Copy dependent rows")

        def in_clause(ids: list, col: str) -> str:
            if not ids:
                return f"WHERE FALSE"
            joined = ",".join(str(int(i)) for i in ids)
            return f"WHERE {col} IN ({joined})"

        plan = [
            ("production.file", in_clause(file_ids, "file_id")),
            ("production.publication", in_clause(pub_ids, "pub_id")),
            ("extsrc.gene", in_clause(ode_gene_ids, "ode_gene_id")),
            ("extsrc.gene_info", in_clause(ode_gene_ids, "ode_gene_id")),
            ("production.geneset", in_clause(gs_ids, "gs_id")),
            ("production.geneset_info", in_clause(gs_ids, "gs_id")),
            ("extsrc.geneset_value", in_clause(gs_ids, "gs_id")),
        ]
        for t, where in plan:
            try:
                copy_table(src, dst, t, where=where)
                with dst.cursor() as c:
                    c.execute(f"SELECT count(*) FROM {t}")
                    print(f"    {t}: {c.fetchone()[0]} rows")
            except Exception as e:
                print(f"    {t}: SKIPPED ({type(e).__name__}: {e})")
                dst.rollback()
                dst.execute("SET session_replication_role = replica")

        print("\n[5/5] Done. Re-enable FK checks.")
        dst.execute("SET session_replication_role = origin")
        dst.commit()


if __name__ == "__main__":
    sys.exit(main())
