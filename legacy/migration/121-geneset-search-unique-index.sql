------------------------------------------------------------------------------------------------------------------------
-- G3-826: nothing refreshes production.geneset_search, so gene sets created since its last
--         rebuild are invisible to the API's gene set search
------------------------------------------------------------------------------------------------------------------------
--
-- `GET /api/genesets/search` does not read the geneset table. It joins production.geneset_search
-- (packages/db/src/geneweaver/db/query/search/search.py:65), the materialized view created by
-- migration 116. A materialized view is a frozen snapshot: its contents change only on REFRESH.
--
-- Nothing in this repository refreshes it: there is no REFRESH MATERIALIZED VIEW anywhere in it
-- -- no SQL, no CronJob, no application code path, no migration after 116. So the view drifts
-- from the tables, and gene sets created since its last rebuild are invisible to the API's search.
--
-- Measured against each database directly on 2026-09-16 (read-only):
--
--                     live gene sets missing   newest gs_created   usable unique
--                     from the view            in the view        index present
--   dev                     19                                    geneset_search_unique_idx
--   sqa                     12                                    geneset_search_unique_idx
--   stage                    1                                    geneset_search_unique_idx
--   prod                    25                   2026-05-06       geneset_search_unique_idx
--
-- On Prod the live table's newest gs_created is 2026-09-15, so the view was last rebuilt between
-- 2026-05-06 and 2026-05-13 (the oldest missing gene set's creation date) -- about four months.
-- The 25 missing rows are gs_id 412712-412744, created 2026-05-13 to 2026-09-15, and they include
-- the reported batch GS412733-GS412741.
--
-- CORRECTION, recorded rather than quietly fixed. The first pass at this said "newest gene set
-- present in the view: GS412582, created 2026-03-02", giving a six-month gap. That was an
-- artifact of how it was measured -- through /api/genesets, which lists only gene sets the caller
-- may SEE. gs_id 412583-412711 are 102 gene sets that are all cur_id 5 (Tier V, private), every
-- one of them present in the view and created 2026-03-03 to 2026-05-06; the enumeration never
-- sampled them, so the newest *visible* row got reported as the newest row. The gap is four
-- months and 25 gene sets, not six months. Nothing about the defect changes -- the reported gene
-- sets are unsearchable and nothing schedules a rebuild -- but the size of it was overstated, and
-- a database that is four months and 25 rows stale is a different thing to plan around than one
-- that is six months stale.
--
-- The failure is silent, which is the part that makes it expensive: the endpoint answers HTTP 200
-- with an empty result set, indistinguishable to a caller from "no such gene set". Nothing logs
-- an error, and the legacy UI's own search (a separate Sphinx index, rebuilt nightly by
-- start_sphinx.sh, G3-814) keeps finding the same gene sets, so nothing points at the API.
--
-- WHY THE INDEX STEP IS HERE AT ALL, GIVEN EVERY DATABASE ALREADY HAS ONE:
--
-- The refresh is the fix; the index is what keeps the refresh affordable. Migration 116 creates only
--     CREATE INDEX geneset_search_idx ON production.geneset_search USING gin(_combined_tsvector);
-- and REFRESH MATERIALIZED VIEW CONCURRENTLY requires at least one UNIQUE index on the view.
-- Without one, the only available form is a plain REFRESH, which holds an ACCESS EXCLUSIVE lock
-- for the whole rebuild -- every API search blocks until it finishes. That is the difference
-- between a nightly job nobody notices and a nightly outage of search, so the recurring job
-- introduced with this ticket (deploy/k8s/base/search-view-refresh-cronjob.yaml) refuses to run
-- at all unless a usable index exists, rather than quietly falling back to the locking form.
--
-- In practice all four databases already carry one (see below), so step 1 creates nothing today
-- and this migration reduces to its catch-up refresh. The step stays because the index is not in
-- any migration -- it exists by some out-of-band act nobody recorded -- so nothing guarantees the
-- next environment, restore or hand-rebuilt view will have it, and the nightly job hard-depends
-- on it. This is the file that makes it a property of the schema rather than a coincidence.
--
-- gs_id is the right key: the view produces exactly one row per non-deleted gene set. Its
-- geneset_query CTE selects from geneset, and its two joins are to publication (keyed on the
-- unique pub_id) and species (unique sp_id), so neither multiplies rows; the gene and ontology
-- CTEs are GROUP BY gs_id and joined LEFT. Step 0 below verifies that on the live data instead
-- of trusting the reading.
--
-- WHAT THE ENVIRONMENTS ACTUALLY LOOK LIKE (measured 2026-09-16, read-only):
--
--   dev   geneset_search_unique_idx (unique btree on gs_id). NO GIN index -- 116's
--         geneset_search_idx on _combined_tsvector is absent, so the full-text predicate the API
--         search runs has no index to use here. Raised separately; not this migration's business.
--   sqa   geneset_search_unique_idx AND geneset_search_idx. Both present.
--   stage geneset_search_unique_idx AND geneset_search_idx. Both present.
--   prod  geneset_search_unique_idx AND geneset_search_idx. Both present.
--
-- So the unique index 116 never created already exists on all four, under the same name on each,
-- and nothing in this repository creates it. dev additionally LOST 116's GIN index, so the
-- full-text predicate the API search runs has no index to use there -- raised separately, not
-- this migration's business. Together those look like the view having been dropped and rebuilt by
-- hand at some point.
--
-- Two consequences. Step 1 must be conditional, and on the index's SHAPE rather than its name.
-- And "CONCURRENTLY is impossible until 121 runs" -- which earlier drafts of this file, the
-- changelog and G3-826 all said -- is true of migration 116 as written and false of every live
-- database. A plain locking REFRESH was never the only option available to an operator here.
--
-- Numbering: 120 is deliberately skipped. It was used on fix/legacy-post-signoff-bugfixes for the
-- G3-809 P/Q threshold boundary split that CLAUDE.md documents, and although that file was later
-- dropped, reusing the number would make two different changes share it across that history.
--
------------------------------------------------------------------------------------------------------------------------
-- SCOPE  -- read before running
------------------------------------------------------------------------------------------------------------------------
--
-- DOES: ensure production.geneset_search has a unique index REFRESH ... CONCURRENTLY can use --
-- creating one on (gs_id) only if no usable one is present, which on all four current databases
-- means creating nothing -- then run the one-off catch-up REFRESH that makes the gene sets above
-- searchable immediately.
--
-- DOES NOT: change any gene set, any threshold, any membership, or any row of production.geneset.
-- Nothing a user has published changes value.
--
-- The view's *contents* do change, by design: the refresh makes the view match the tables it is
-- derived from. That is a change in what API search returns, in BOTH directions, and not only an
-- addition:
--
--   * gene sets created since the last build start being returned -- the point of this migration;
--   * gene sets DELETED since the last build, or edited so they no longer match a query, stop
--     being returned. The view's own definition is `WHERE gs.gs_status <> 'deleted'` (116), so a
--     gene set deleted after the last build is still in the stale view and still findable today.
--
-- So the row count can fall, and results a user could find yesterday can be gone tomorrow. Those
-- are stale rows the view should not have been serving -- a deleted gene set appearing in search
-- results is the same staleness bug pointing the other way -- but they are a real change in
-- output, not a no-op. This is why jobs/refresh_search_view.py tolerates a shrinking row count
-- and fails only on an empty view: a decrease is legitimate, an empty view never is.
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
--     the view and it is not quick.
--
--     MEASURED on dev, 2026-09-16: 526.7s -- 8 minutes 47 seconds -- on a 261,005-row view, to
--     add 19 rows. Note the shape of that: nearly nine minutes of work to publish nineteen gene
--     sets. The cost is rebuilding the whole aggregate and is essentially independent of how
--     stale the view is, so it does not shrink once the backlog is cleared and the nightly job
--     will pay roughly this every night. Prod's view is slightly larger (264,730 rows) over a
--     larger geneset_value, so budget more there. Both sit comfortably inside the nightly job's
--     55-minute statement_timeout, and comfortably inside the two-hour stagger between the
--     environments that share a Cloud SQL instance. Prefer a quiet window anyway.
--
--     It is deliberately OUTSIDE the transaction: REFRESH MATERIALIZED VIEW
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

-- 1) Apply: ensure the view has a unique index REFRESH ... CONCURRENTLY can use.
--
--    Conditional, and NOT `CREATE UNIQUE INDEX IF NOT EXISTS geneset_search_gs_id_idx`, because
--    IF NOT EXISTS keys off the NAME. Measured 2026-09-16, dev and sqa already carry
--        CREATE UNIQUE INDEX geneset_search_unique_idx ON production.geneset_search USING btree (gs_id)
--    which is unique, valid, immediate, non-partial and over a plain column -- already exactly
--    what CONCURRENTLY needs. It does not come from migration 116 and its provenance is unknown
--    (see the note below), but it is there, so a name-keyed IF NOT EXISTS would have added a
--    SECOND unique index on the same column: one more btree to maintain on every refresh, for
--    nothing. What this migration needs to guarantee is the index's existence and shape, not its
--    name, so it tests for that and creates one only where none is usable.
DO $$
DECLARE
    usable text;
BEGIN
    SELECT i.relname INTO usable
    FROM pg_index x
    JOIN pg_class i ON i.oid = x.indexrelid
    JOIN pg_class t ON t.oid = x.indrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'production'
      AND t.relname = 'geneset_search'
      AND x.indisunique
      AND x.indisvalid
      AND x.indimmediate
      AND x.indpred IS NULL
      AND x.indexprs IS NULL
    LIMIT 1;

    IF usable IS NOT NULL THEN
        RAISE NOTICE 'geneset_search already has a usable unique index (%); leaving it alone', usable;
    ELSE
        CREATE UNIQUE INDEX geneset_search_gs_id_idx ON production.geneset_search (gs_id);
        RAISE NOTICE 'created geneset_search_gs_id_idx';
    END IF;
END $$;

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
