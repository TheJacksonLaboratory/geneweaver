------------------------------------------------------------------------------------------------------------------------
-- CHECK ONLY -- gs_count drift (GWC-34 / G3-782).  Read-only: writes nothing.
------------------------------------------------------------------------------------------------------------------------
--
-- Files in this directory are diagnostics, not migrations. Numbered files one level up
-- (`legacy/migration/NNN-*.sql`) change data; these only report on it, so they are safe
-- to run in any environment at any time, including Prod during business hours.
--
-- Purpose: answer "does this environment have the GWC-34 problem, and how badly?"
--
-- Background. Search and the My Genesets Count column render the stored
-- production.geneset.gs_count. The geneset page instead counts extsrc.geneset_value live
-- (geneweaverdb.get_genecount_in_geneset). When a write path stores a gs_count that was
-- not derived from those rows, the two disagree. All three known causes over-count, so a
-- healthy environment should show zero drift in section 1.
--
-- Run (Cloud SQL Auth proxy + local psql):
--   cloud-sql-proxy <project>:<region>:<instance> --port 5433 &
--   psql "host=127.0.0.1 port=5433 dbname=<db> user=<user>" \
--        -f legacy/migration/checks/gwc34-gs-count-drift.sql
--
-- NOTE: the `geneweaver-legacy` pods have no psql client installed, so the
-- `kubectl exec ... psql` pattern used elsewhere in the release plan does not work for
-- them. They do have Python + psycopg2 and the DB_* environment, so a pod-side run means
-- feeding the statements below through python3 instead. The proxy route above is simpler.
--
-- Cost: aggregates extsrc.geneset_value once (~35M rows / ~20s on dev; expect longer on
-- Prod). It is a plain sequential scan -- no locks taken beyond a read.
--
-- Reading the result:
--   Section 1 non-zero  -> genesets are miscounted. Run migration 118 on this database.
--                          If it is non-zero on an environment where 118 has ALREADY run,
--                          the code fix is missing or has regressed -- check that the
--                          deployed image contains the uploadfiles.py / genesetblueprint.py
--                          fixes before backfilling again, or it will just drift back.
--   Section 2 non-zero  -> genesets that claim genes but hold none. Migration 118 does
--                          NOT touch these by design; they are a separate, unresolved
--                          issue (bad source files, missing gene data) and are not
--                          repairable by re-running the resolver. See CHANGELOG "Known
--                          issues".
--   Section 3           -> whether the backfill has been run here, and when.

\pset pager off

\echo
\echo ==== 1. Miscounted genesets (have genes, wrong gs_count) -- migration 118 fixes these
WITH v AS (SELECT gs_id, count(*) AS real_rows FROM extsrc.geneset_value GROUP BY gs_id)
SELECT count(*)                                   AS genesets_wrong,
       COALESCE(sum(gs.gs_count - v.real_rows),0) AS phantom_genes,
       COALESCE(max(gs.gs_count - v.real_rows),0) AS worst_single,
       count(*) FILTER (WHERE gs.gs_count < v.real_rows) AS under_counted
FROM production.geneset gs
JOIN v ON v.gs_id = gs.gs_id
WHERE gs.gs_count IS DISTINCT FROM v.real_rows
  AND (gs.gs_status IS NULL OR gs.gs_status NOT LIKE 'delayed%');

\echo
\echo ---- the offenders (top 20 by size of the error)
WITH v AS (SELECT gs_id, count(*) AS real_rows FROM extsrc.geneset_value GROUP BY gs_id)
SELECT gs.gs_id, gs.gs_count AS says, v.real_rows AS actually,
       gs.gs_count - v.real_rows AS gap, gs.gs_status, gs.gs_created,
       left(gs.gs_name, 40) AS name
FROM production.geneset gs
JOIN v ON v.gs_id = gs.gs_id
WHERE gs.gs_count IS DISTINCT FROM v.real_rows
  AND (gs.gs_status IS NULL OR gs.gs_status NOT LIKE 'delayed%')
ORDER BY abs(gs.gs_count - v.real_rows) DESC
LIMIT 20;

\echo
\echo ==== 2. Genesets claiming genes but holding none -- NOT touched by migration 118
SELECT CASE WHEN gs.gs_status IS NULL             THEN '(null)'
            WHEN gs.gs_status LIKE 'normal%'      THEN 'normal  <- user visible'
            WHEN gs.gs_status LIKE 'deleted%'     THEN 'deleted'
            WHEN gs.gs_status LIKE 'delayed%'     THEN 'delayed (in flight)'
            WHEN gs.gs_status LIKE 'deprecated%'  THEN 'deprecated'
            ELSE 'other' END AS status,
       count(*) AS genesets, max(gs.gs_count) AS worst_claim
FROM production.geneset gs
LEFT JOIN (SELECT gs_id, count(*) AS n FROM extsrc.geneset_value GROUP BY gs_id) v
       ON v.gs_id = gs.gs_id
WHERE COALESCE(v.n, 0) = 0 AND gs.gs_count > 0
GROUP BY 1
ORDER BY 2 DESC;

\echo
\echo ==== 3. Has migration 118 been applied to this database?
-- The audit table is resolved when the statement is parsed, so it cannot simply be
-- SELECTed behind a to_regclass() guard -- that still errors when the table is absent,
-- which is precisely the case being tested. Hence the dynamic lookup.
DO $$
DECLARE n bigint; first_run timestamp; last_run timestamp;
BEGIN
  IF to_regclass('production.gwc34_118_gs_count_audit') IS NULL THEN
    RAISE NOTICE 'migration 118 has NOT been applied to this database';
  ELSE
    EXECUTE 'SELECT count(*), min(captured_at), max(captured_at) '
            'FROM production.gwc34_118_gs_count_audit'
       INTO n, first_run, last_run;
    RAISE NOTICE 'migration 118 applied: % genesets corrected (first %, last %)',
                 n, first_run, last_run;
  END IF;
END $$;
