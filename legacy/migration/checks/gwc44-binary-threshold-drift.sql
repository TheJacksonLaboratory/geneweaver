------------------------------------------------------------------------------------------------------------------------
-- CHECK ONLY -- binary in-threshold drift (GWC-44 / G3-776).  Read-only: writes nothing.
------------------------------------------------------------------------------------------------------------------------
--
-- Files in this directory are diagnostics, not migrations. Numbered files one level up
-- (`legacy/migration/NNN-*.sql`) change data; these only report on it, so they are safe
-- to run in any environment at any time, including Prod during business hours.
--
-- Purpose: answer two questions for an environment -- "is migration 117 applied here?" and
-- "are any binary gene sets still thresholded-out?" -- without a migration ledger to ask.
--
-- Background. production.process_thresholds is a *database* object, so an environment can
-- run the correct application image and still carry the unpatched procedure. When it does,
-- nothing errors: process_thresholds evaluated Binary (gs_threshold_type = 3) as
-- `gsv_value > gs_threshold`, i.e. `value > 1` for the default binary threshold, so every
-- 0/1 value was flagged gsv_in_threshold = FALSE. Every analysis tool and in-threshold
-- count filters on gsv_in_threshold, so the whole binary set silently becomes invisible /
-- unusable -- even a plain all-1 membership list. Migration 117 (GWC-44) fixes the
-- procedure (Binary -> always in-threshold) and backfills the existing rows.
--
-- This is the detection half of the deploy-ordering hazard the release plan flags in
-- §5.2: the code alone is not enough, because the UI upload path and the threshold-change
-- trigger both call this *database* procedure.
--
-- Run (Cloud SQL Auth proxy + local psql):
--   cloud-sql-proxy <project>:<region>:<instance> --port 5433 &
--   psql "host=127.0.0.1 port=5433 dbname=<db> user=<user>" \
--        -f legacy/migration/checks/gwc44-binary-threshold-drift.sql
--
-- NOTE: the `geneweaver-legacy` pods have no psql client installed, so the
-- `kubectl exec ... psql` pattern used elsewhere in the release plan does not work for
-- them. They do have Python + psycopg2 and the DB_* environment, so a pod-side run means
-- feeding the statements below through python3 instead. The proxy route above is simpler.
--
-- Cost: section 1 aggregates extsrc.geneset_value once (~34M rows / ~25s on dev; expect
-- longer on Prod). It is a plain sequential scan -- no locks taken beyond a read.
--
-- Reading the result -- the three sections together, not in isolation:
--   Section 2 FALSE          -> the stored procedure is UNPATCHED. Binary sets are broken
--                               here AND every new binary upload will break too, whatever
--                               image is deployed. Run migration 117 on this database.
--   Section 2 TRUE,          -> the procedure is fixed, so new uploads are correct, but the
--     section 1 non-zero        one-time backfill of PRE-EXISTING sets has not run (or has
--                               drifted). Run migration 117's step-2 backfill. If section 3
--                               says the backfill already ran here, something re-thresholded
--                               those rows afterwards -- investigate before backfilling again.
--   Section 2 TRUE,          -> healthy: 117 fully applied, or this environment simply has
--     section 1 zero            no binary gene sets to fix.
--   Section 3                -> whether the backfill has been captured/run here, and when.

\pset pager off

\echo
\echo ==== 1. Binary gene sets still holding out-of-threshold values -- migration 117 fixes these
-- Matches migration 117's own backfill predicate exactly, so `rows_to_change` is precisely
-- what the migration would touch (and what its §5.1 audit-capture step would record).
SELECT count(*)                     AS rows_to_change,
       count(DISTINCT gv.gs_id)     AS binary_sets
FROM extsrc.geneset_value gv
JOIN production.geneset gs ON gs.gs_id = gv.gs_id
WHERE gs.gs_threshold_type = 3
  AND gv.gsv_in_threshold IS DISTINCT FROM TRUE;

\echo
\echo ---- the offenders (top 20 binary sets by out-of-threshold rows; status shows user impact)
SELECT gs.gs_id,
       count(*)                                          AS out_of_threshold_rows,
       (SELECT count(*) FROM extsrc.geneset_value v
        WHERE v.gs_id = gs.gs_id)                        AS total_rows,
       gs.gs_status,
       gs.gs_created,
       left(gs.gs_name, 40)                              AS name
FROM extsrc.geneset_value gv
JOIN production.geneset gs ON gs.gs_id = gv.gs_id
WHERE gs.gs_threshold_type = 3
  AND gv.gsv_in_threshold IS DISTINCT FROM TRUE
GROUP BY gs.gs_id, gs.gs_status, gs.gs_created, gs.gs_name
ORDER BY out_of_threshold_rows DESC
LIMIT 20;

\echo
\echo ==== 2. Is production.process_thresholds patched? (distinguishes "clean" from "no binary sets here")
-- The patched procedure resolves the Binary branch to a literal TRUE; the pre-fix one
-- compared gsv_value against the threshold. pg_get_functiondef normalises whitespace, so
-- the wildcards absorb the newline/indentation between THEN and TRUE.
SELECT pg_get_functiondef('production.process_thresholds(bigint)'::regprocedure)
       LIKE '%WHEN gs_threshold_type=3 THEN%TRUE%' AS proc_patched;

\echo
\echo ==== 3. Has migration 117's backfill been captured/run on this database?
-- The audit table is resolved when the statement is parsed, so it cannot simply be
-- SELECTed behind a to_regclass() guard -- that still errors when the table is absent,
-- which is precisely the case being tested. Hence the dynamic lookup. (The audit table is
-- created by the release plan's §5.1 capture step, not by the migration file itself.)
DO $$
DECLARE n bigint; sets bigint; first_run timestamptz; last_run timestamptz;
BEGIN
  IF to_regclass('production.gwc44_117_backfill_audit') IS NULL THEN
    RAISE NOTICE 'migration 117 backfill audit NOT present on this database';
  ELSE
    EXECUTE 'SELECT count(*), count(DISTINCT gs_id), min(captured_at), max(captured_at) '
            'FROM production.gwc44_117_backfill_audit'
       INTO n, sets, first_run, last_run;
    RAISE NOTICE 'migration 117 backfill captured: % rows across % binary sets (first %, last %)',
                 n, sets, first_run, last_run;
  END IF;
END $$;
