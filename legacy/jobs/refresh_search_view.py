#!/usr/bin/env python3
"""Refresh production.geneset_search, the materialized view the API's gene set search reads.

Run by the geneweaver-search-view-refresh CronJob (deploy/k8s/base/search-view-refresh-cronjob.yaml),
nightly, alongside the legacy search sidecar's own nightly full rebuild (start_sphinx.sh, G3-814).
GeneWeaver has two independent search indexes over the same data and this is the scheduler the
second one was missing:

  * legacy UI search  -> Sphinx/Manticore index, rebuilt in the geneweaver-legacy-search sidecar
  * GET /api/genesets/search -> production.geneset_search, a MATERIALIZED VIEW (migration 116)

A materialized view only changes on REFRESH. Direct database checks on 2026-09-16 found 25 live
Prod gene sets missing from this one: the newest materialized ``gs_created`` was 2026-05-06 while
the live table had reached 2026-09-15. The API answered searches for the missing sets with an empty
result set and HTTP 200, indistinguishable to a caller from "no such gene set". See G3-826.

CONCURRENTLY is not optional here. The plain form holds an ACCESS EXCLUSIVE lock for the whole
rebuild, which would take API search down for as long as the refresh runs; CONCURRENTLY builds the
new contents alongside the old and swaps them, so readers keep being served throughout. It requires
a unique index on the view, which migration 121 adds -- and which this script insists on rather
than falling back to the locking form, because a nightly job that silently blocks search for
minutes is worse than a nightly job that fails loudly with the reason.

The refresh is atomic: if it fails or the pod is killed part-way, the view keeps its previous
contents. A failed run therefore costs freshness until the next run, never availability.
"""

import os
import sys
import time

import psycopg2

# Not user input and not parameterisable -- an identifier cannot be bound as a parameter. Held as a
# constant so the one privileged statement in this job is stated in exactly one place.
VIEW_SCHEMA = "production"
VIEW_NAME = "geneset_search"
REFRESH_SQL = f"REFRESH MATERIALIZED VIEW CONCURRENTLY {VIEW_SCHEMA}.{VIEW_NAME}"

# The DB aborts the refresh before Kubernetes' activeDeadlineSeconds kills the pod, so a run that
# overruns its budget reports a Postgres timeout rather than a bare SIGKILL with no explanation.
# The CronJob's activeDeadlineSeconds is 60 minutes. Preserve a five-minute margin even when an
# operator supplies an override, so Postgres reports a useful timeout before Kubernetes kills the
# pod. PostgreSQL treats zero as "disabled", so the lower bound matters too.
MAX_STATEMENT_TIMEOUT_MS = 3_300_000  # 55 minutes
DEFAULT_STATEMENT_TIMEOUT_MS = MAX_STATEMENT_TIMEOUT_MS


def log(message: str) -> None:
    """Write a progress line. Never called with any part of the DB password."""
    print(f"search-view-refresh: {message}")


def connect():
    """Connect using the DB_* environment the geneweaver-db secret provides.

    Every value comes from the environment -- nothing about the instance is baked in here, so the
    same image runs against dev, sqa, stage and prod unchanged.
    """
    missing = [v for v in ("DB_HOST", "DB_NAME", "DB_USERNAME", "DB_PASSWORD") if not os.environ.get(v)]
    if missing:
        raise SystemExit(
            f"search-view-refresh: missing required environment: {', '.join(missing)}. "
            "The job expects the geneweaver-db secret to be mounted with envFrom."
        )

    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USERNAME"],
        password=os.environ["DB_PASSWORD"],
    )
    # REFRESH MATERIALIZED VIEW CONCURRENTLY cannot run inside a transaction block, and psycopg2
    # opens one implicitly on the first execute. Without this the refresh fails outright.
    conn.autocommit = True
    # Log where we connected, but never the credentials.
    log(f"connected to {os.environ['DB_NAME']} at {os.environ['DB_HOST']} as {os.environ['DB_USERNAME']}")
    return conn


def require_unique_index(cursor) -> None:
    """Refuse to run unless an index REFRESH ... CONCURRENTLY can actually use is present.

    Falling back to a plain REFRESH would work, and would block every API search for the duration
    of the rebuild. Failing here instead leaves search stale but responsive, and names the reason.

    "Unique and valid" is NOT the requirement. Postgres accepts CONCURRENTLY only with a unique
    index that "uses only column names and includes all rows" -- so an expression index or a
    partial (WHERE ...) index does not qualify, and nor does a non-immediate one. Checking only
    indisunique/indisvalid would let this guard pass and the REFRESH fail immediately afterwards
    with a message about the index rather than about the migration, which defeats the whole point
    of guarding. The predicates below are the same four properties Postgres itself requires.
    """
    cursor.execute(
        """
        SELECT i.relname
        FROM pg_index x
        JOIN pg_class i ON i.oid = x.indexrelid
        JOIN pg_class t ON t.oid = x.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = %s
          AND t.relname = %s
          AND x.indisunique
          AND x.indisvalid
          AND x.indimmediate
          AND x.indpred IS NULL
          AND x.indexprs IS NULL
        """,
        (VIEW_SCHEMA, VIEW_NAME),
    )
    indexes = [row[0] for row in cursor.fetchall()]
    if not indexes:
        raise SystemExit(
            f"search-view-refresh: {VIEW_SCHEMA}.{VIEW_NAME} has no unique index that REFRESH "
            "MATERIALIZED VIEW CONCURRENTLY can use -- it must be unique, valid, immediate, and "
            "over plain columns with no WHERE clause. Apply migration "
            "121-geneset-search-unique-index.sql to this environment. Refusing to fall back to a "
            "plain REFRESH, which would hold ACCESS EXCLUSIVE and block API search for the whole "
            "rebuild."
        )
    log(f"usable unique index present: {', '.join(indexes)}")


def state(cursor) -> tuple:
    """Return (row_count, newest_gs_id) currently materialised in the view."""
    cursor.execute(f"SELECT count(*), max(gs_id) FROM {VIEW_SCHEMA}.{VIEW_NAME}")
    return cursor.fetchone()


def statement_timeout_ms() -> int:
    """Read and validate the timeout while preserving the CronJob's safety margin."""
    raw = os.environ.get(
        "SEARCH_VIEW_REFRESH_STATEMENT_TIMEOUT_MS",
        str(DEFAULT_STATEMENT_TIMEOUT_MS),
    )
    try:
        timeout_ms = int(raw)
    except ValueError:
        raise SystemExit(
            "search-view-refresh: SEARCH_VIEW_REFRESH_STATEMENT_TIMEOUT_MS must be an "
            f"integer from 1 through {MAX_STATEMENT_TIMEOUT_MS}; got {raw!r}"
        ) from None

    if not 1 <= timeout_ms <= MAX_STATEMENT_TIMEOUT_MS:
        raise SystemExit(
            "search-view-refresh: SEARCH_VIEW_REFRESH_STATEMENT_TIMEOUT_MS must be from "
            f"1 through {MAX_STATEMENT_TIMEOUT_MS} so Postgres times out before the "
            f"CronJob deadline; got {timeout_ms}"
        )
    return timeout_ms


def main() -> int:
    timeout_ms = statement_timeout_ms()

    conn = connect()
    with conn.cursor() as cursor:
        cursor.execute("SET statement_timeout = %s", (timeout_ms,))
        log(f"statement_timeout set to {timeout_ms} ms")

        require_unique_index(cursor)

        rows_before, newest_before = state(cursor)
        log(f"before: {rows_before} rows, newest gs_id {newest_before}")

        started = time.monotonic()
        cursor.execute(REFRESH_SQL)
        elapsed = time.monotonic() - started

        rows_after, newest_after = state(cursor)
        log(f"after:  {rows_after} rows, newest gs_id {newest_after}")
        log(
            f"refreshed in {elapsed:.1f}s "
            f"({rows_after - rows_before:+d} rows, newest gs_id {newest_before} -> {newest_after})"
        )

        # The row count can legitimately fall -- the view excludes deleted gene sets, so deletions
        # since the last refresh remove rows. An EMPTY view cannot be legitimate, and would mean
        # search returns nothing at all for everyone, so treat only that as a failure.
        if not rows_after:
            log("FAILED: the view is empty after refreshing; API search would return nothing")
            return 1

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
