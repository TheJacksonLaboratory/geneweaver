#!/usr/bin/env python3
"""Refresh production.geneset_search, the materialized view the API's gene set search reads.

Run by the geneweaver-search-view-refresh CronJob (deploy/k8s/base/search-view-refresh-cronjob.yaml),
nightly, alongside the legacy search sidecar's own nightly full rebuild (start_sphinx.sh, G3-814).
GeneWeaver has two independent search indexes over the same data and this is the scheduler the
second one was missing:

  * legacy UI search  -> Sphinx/Manticore index, rebuilt in the geneweaver-legacy-search sidecar
  * GET /api/genesets/search -> production.geneset_search, a MATERIALIZED VIEW (migration 116)

A materialized view only changes on REFRESH. Nothing ever refreshed this one, so by 2026-09-16 the
newest gene set it contained was GS412582 (created 2026-03-02) while the database had gone on to
GS412741 (2026-09-14) -- six months of new gene sets that the API's search answered with an empty
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
# Keep this below the CronJob's activeDeadlineSeconds.
DEFAULT_STATEMENT_TIMEOUT_MS = 3_300_000  # 55 minutes


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
    """Refuse to run unless migration 121's unique index is present.

    Falling back to a plain REFRESH would work, and would block every API search for the duration
    of the rebuild. Failing here instead leaves search stale but responsive, and names the reason.
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
        """,
        (VIEW_SCHEMA, VIEW_NAME),
    )
    indexes = [row[0] for row in cursor.fetchall()]
    if not indexes:
        raise SystemExit(
            f"search-view-refresh: {VIEW_SCHEMA}.{VIEW_NAME} has no valid unique index, so it "
            "cannot be refreshed CONCURRENTLY. Apply migration "
            "121-geneset-search-unique-index.sql to this environment. Refusing to fall back to a "
            "plain REFRESH, which would hold ACCESS EXCLUSIVE and block API search for the whole "
            "rebuild."
        )
    log(f"unique index present: {', '.join(indexes)}")


def state(cursor) -> tuple:
    """Return (row_count, newest_gs_id) currently materialised in the view."""
    cursor.execute(f"SELECT count(*), max(gs_id) FROM {VIEW_SCHEMA}.{VIEW_NAME}")
    return cursor.fetchone()


def main() -> int:
    timeout_ms = int(os.environ.get("SEARCH_VIEW_REFRESH_STATEMENT_TIMEOUT_MS", DEFAULT_STATEMENT_TIMEOUT_MS))

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
