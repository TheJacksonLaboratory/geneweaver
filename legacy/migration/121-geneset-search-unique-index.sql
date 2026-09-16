------------------------------------------------------------------------------------------------------------------------
-- G3-826: production.geneset_search has no unique index, so it cannot be refreshed
--         without locking out the API's geneset search
------------------------------------------------------------------------------------------------------------------------
--
-- `GET /api/genesets/search` does not read the geneset table. It joins production.geneset_search
-- (packages/db/src/geneweaver/db/query/search/search.py:65), the materialized view created by
-- migration 116. A materialized view is a frozen snapshot: its contents change only on REFRESH.
--
-- Nothing has ever refreshed it. There is no REFRESH MATERIALIZED VIEW anywhere in the
-- repository -- no SQL, no CronJob, no application code path -- so the view still holds whatever
-- the database contained when 116 was applied, and every gene set created since is invisible to
-- the API's search. Measured against Prod on 2026-09-16 through the API:
--
--   newest gene set present in the view : GS412582, created 2026-03-02
--   oldest gene set missing from it     : GS412733, created 2026-09-14
--
-- and all nine gene sets of the 2026-09-14 upload batch (GS412733-GS412741) are missing. The
-- failure is silent: the endpoint answers HTTP 200 with an empty result set, which a caller
-- cannot distinguish from "no such gene set". Samples from 2019, 2023, 2025 and early 2026 are
-- all present, so the view is stale rather than broken.
--
-- WHY AN INDEX FIXES NOTHING BY ITSELF -- and is still the thing to do first:
--
-- The refresh is the fix; this migration makes the refresh affordable. Migration 116 creates only
--     CREATE INDEX geneset_search_idx ON production.geneset_search USING gin(_combined_tsvector);
-- and REFRESH MATERIALIZED VIEW CONCURRENTLY requires at least one UNIQUE index on the view.
-- Without one, the only available form is a plain REFRESH, which holds an ACCESS EXCLUSIVE lock
-- for the whole rebuild -- every API search blocks until it finishes. That is the difference
-- between a nightly job nobody notices and a nightly outage of search, so the recurring job
-- introduced with this ticket (deploy/k8s/base/search-view-refresh-cronjob.yaml) refuses to run
-- at all unless this index exists, rather than quietly falling back to the locking form.
--
-- gs_id is the right key: the view produces exactly one row per non-deleted gene set. Its
-- geneset_query CTE selects from geneset, and its two joins are to publication (keyed on the
-- unique pub_id) and species (unique sp_id), so neither multiplies rows; the gene and ontology
-- CTEs are GROUP BY gs_id and joined LEFT. Step 0 below verifies that on the live data instead
-- of trusting the reading.
--
-- Numbering: 120 is deliberately skipped. It was used on fix/legacy-post-signoff-bugfixes for the
-- G3-809 P/Q threshold boundary split that CLAUDE.md documents, and although that file was later
-- dropped, reusing the number would make two different changes share it across that history.
--
------------------------------------------------------------------------------------------------------------------------
-- SCOPE  -- read before running
------------------------------------------------------------------------------------------------------------------------
--
-- DOES: add one unique btree index on production.geneset_search (gs_id), then run the one-off
-- catch-up REFRESH that makes the gene sets above searchable immediately.
--
-- DOES NOT: change any gene set, any threshold, any membership, or any row of production.geneset.
-- Nothing a user has published changes value. The view's *contents* change -- by design, to match
-- the tables it is derived from -- so search starts returning gene sets it has been omitting.
-- Nothing that search returns today stops being returned: the view is rebuilt from the same
-- definition against a superset of the data it was built from.
--
-- Idempotent? Yes. The index is created IF NOT EXISTS, and a REFRESH can be run any number of
-- times. Reversible? Yes -- see Rollback. No audit table is needed because no user data is
-- written; the view is derived data and is rebuilt from its sources.
--
-- Cost, and why the two steps are split:
--
--   * Step 1 (the index) takes a brief ACCESS EXCLUSIVE lock on the view -- one btree over one
--     row per non-deleted gene set (gs_id values currently reach ~412,700), which is seconds.
--     API search blocks for that long. It is inside the transaction below.
--   * Step 3 (the catch-up refresh) is the expensive half: CONCURRENTLY rebuilds the whole view,
--     and the view aggregates extsrc.geneset_value (~35M rows) joined to gene and gene_info plus
--     the ontology aggregate. It does NOT block readers, but it needs room for a second copy of
--     the view and it is not quick. Time it on dev/stage before running it on prod, and prefer a
--     quiet window. It is deliberately OUTSIDE the transaction: REFRESH MATERIALIZED VIEW
--     CONCURRENTLY cannot run inside a transaction block, so do not apply this file with
--     `psql --single-transaction` -- step 3 will fail with
--     "REFRESH MATERIALIZED VIEW CONCURRENTLY cannot be executed from a function or
--     multi-command string". Apply it plainly (`psql -v ON_ERROR_STOP=1 -f 121-...sql`).
--
-- After this, the recurring CronJob keeps the view current; this migration only closes the gap
-- that has already accumulated.

BEGIN;

-- 0) The unique index can only be created if gs_id really is unique in the view. This must
--    return ZERO rows. If it does not, stop: the view definition in 116 is producing duplicate
--    rows per gene set, which is a separate bug and would also mean the API's search has been
--    returning duplicates.
SELECT gs_id, count(*) AS rows_for_this_geneset
FROM production.geneset_search
GROUP BY gs_id
HAVING count(*) > 1;

-- 1) Apply: the unique index that makes REFRESH ... CONCURRENTLY possible.
CREATE UNIQUE INDEX IF NOT EXISTS geneset_search_gs_id_idx
    ON production.geneset_search (gs_id);

-- 2) Verify: must return exactly one row, indisunique = true.
SELECT i.relname AS index_name, x.indisunique, x.indisvalid
FROM pg_index x
JOIN pg_class i ON i.oid = x.indexrelid
JOIN pg_class t ON t.oid = x.indrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
WHERE n.nspname = 'production'
  AND t.relname = 'geneset_search'
  AND x.indisunique;

COMMIT;

------------------------------------------------------------------------------------------------------------------------
-- Step 3: the one-off catch-up refresh.  MUST run outside a transaction block (see Cost above).
------------------------------------------------------------------------------------------------------------------------
-- Record what the stale view holds, so the before/after is on the record for this environment.
SELECT count(*) AS rows_before, max(gs_id) AS newest_gs_id_before FROM production.geneset_search;

REFRESH MATERIALIZED VIEW CONCURRENTLY production.geneset_search;

SELECT count(*) AS rows_after, max(gs_id) AS newest_gs_id_after FROM production.geneset_search;

-- 4) Verify the reported case is now searchable. On an environment that has GS412733 (Prod) this
--    must return one row; elsewhere it returns none and the two counts above are the evidence.
SELECT gs_id
FROM production.geneset_search
WHERE _combined_tsvector @@ plainto_tsquery('english', 'gs412733');

-- 5) And that nothing that used to be findable was lost -- GS412582 was the newest row in the
--    stale view. Must return one row.
SELECT gs_id
FROM production.geneset_search
WHERE _combined_tsvector @@ plainto_tsquery('english', 'gs412582');

------------------------------------------------------------------------------------------------------------------------
-- Rollback
------------------------------------------------------------------------------------------------------------------------
-- Dropping the index returns the view to the state 116 left it in. It does NOT un-refresh the
-- view -- a refresh cannot be undone, and there is nothing to undo: the view's job is to match
-- the tables, and after step 3 it does. If the recurring CronJob is also removed, the view simply
-- goes stale again from that point on.
--
-- BEGIN;
-- DROP INDEX IF EXISTS production.geneset_search_gs_id_idx;
-- COMMIT;
