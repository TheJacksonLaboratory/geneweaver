------------------------------------------------------------------------------------------------------------------------
-- GWC-34 / G3-782: gs_count disagrees with the genes a geneset actually contains
------------------------------------------------------------------------------------------------------------------------
--
-- Search and the "View My Genesets" Count column render production.geneset.gs_count.
-- The geneset page instead runs its own count(*) over extsrc.geneset_value
-- (geneweaverdb.get_genecount_in_geneset). Three write paths stored a gs_count that was
-- never derived from those rows, so the two numbers disagreed:
--
--   1. uploadfiles.create_new_geneset_for_user -- passed len(gene_data.split('\n')) to
--      production.create_geneset2, which stores it verbatim and only afterwards calls
--      reparse_geneset_file() to resolve identifiers. That counted submitted *lines*,
--      including the trailing blank line split('\n') yields for text ending in a
--      newline, while geneset_value holds one row per distinct identifier that resolved.
--   2. uploadfiles.insert_into_geneset_value_by_gsid -- counted production.temp_geneset_value
--      (staged rows) while the INSERT groups by ode_gene_id. Fixed in a133bd2b.
--   3. genesetblueprint create_temp_geneset / create_geneset -- counted
--      `geneset_value NATURAL JOIN gene WHERE ode_pref`, i.e. one row per preferred
--      identifier a gene carries (avg ~2 on dev), roughly doubling the count.
--
-- All three can only over-count, matching the data: on dev no geneset is under-counted.
-- The code fixes stop new genesets drifting; this corrects rows that are already wrong.
-- Reference case GS407881: 8 identifiers submitted, gs_count 9, 4 genes actually stored.
--
------------------------------------------------------------------------------------------------------------------------
-- WHAT THIS DOES AND DOES NOT FIX  -- read before running
------------------------------------------------------------------------------------------------------------------------
--
-- FIXES: genesets that have at least one row in extsrc.geneset_value whose gs_count
-- disagrees with those rows. On dev that is 33 genesets, all gs_status 'normal',
-- 1,792 phantom genes in total. GS407881 is in this set.
--
-- DOES NOT FIX: genesets with gs_count > 0 and *zero* geneset_value rows -- 78,203 on
-- dev, of which 2,920 carry a live ('normal'/null) status and are therefore visible in
-- search, one of them claiming 13,190 genes. These are a different failure: not a
-- miscounted geneset but an empty one advertising content. Whether they should read 0,
-- be hidden, or be repaired from their stored file is an open product question raised
-- with the reporter on GWC-34 and still unanswered, and zeroing them would silently
-- change what search returns for ~1.5% of the live corpus. Handle them in a separate
-- migration once that is decided.
--
-- So after this runs, a user can still find a geneset whose search count does not match
-- its page -- it will be one of the empty ones, not a miscount.
--
-- Idempotent? Yes -- it only rewrites rows that currently disagree; a second run matches
-- nothing. Reversible? Yes, via the audit table captured in step 1.
--
-- Cost: extsrc.geneset_value is ~35M rows on dev and larger on prod, so the per-geneset
-- aggregate is materialised ONCE below and reused by every step rather than recomputed.
-- Expect one sequential scan of geneset_value. If that is too long a transaction on
-- prod, run steps 0-1 outside the transaction and batch step 2 by gs_id range.

BEGIN;

-- Materialise the per-geneset gene counts once. ANALYZE so the planner costs the joins
-- below against real statistics rather than the default guess for a fresh temp table.
CREATE TEMP TABLE gwc34_real_counts ON COMMIT DROP AS
SELECT gs_id, count(*)::bigint AS real_rows
FROM extsrc.geneset_value
GROUP BY gs_id;

CREATE UNIQUE INDEX ON gwc34_real_counts (gs_id);
ANALYZE gwc34_real_counts;

-- 0) Size it first.
--    'delayed%' genesets are excluded throughout: they are mid-upload, their rows are
--    still being written, and uploadfiles.insert_into_geneset_value_by_gsid sets the
--    correct gs_count when the upload commits. Rewriting them here would race that.
SELECT count(*)                       AS genesets_to_fix,
       sum(gs.gs_count - v.real_rows) AS total_overcount,
       max(gs.gs_count - v.real_rows) AS worst_overcount
FROM production.geneset gs
JOIN gwc34_real_counts v ON v.gs_id = gs.gs_id
WHERE gs.gs_count IS DISTINCT FROM v.real_rows
  AND (gs.gs_status IS NULL OR gs.gs_status NOT LIKE 'delayed%');

-- 1) Capture the pre-state so the backfill can be undone (do this in every environment).
--    Not a TEMP table -- it must outlive the transaction to be useful for rollback.
CREATE TABLE IF NOT EXISTS production.gwc34_118_gs_count_audit (
    gs_id         bigint PRIMARY KEY,
    prev_gs_count integer,
    new_gs_count  bigint,
    captured_at   timestamp
);

INSERT INTO production.gwc34_118_gs_count_audit (gs_id, prev_gs_count, new_gs_count, captured_at)
SELECT gs.gs_id, gs.gs_count, v.real_rows, now()
FROM production.geneset gs
JOIN gwc34_real_counts v ON v.gs_id = gs.gs_id
WHERE gs.gs_count IS DISTINCT FROM v.real_rows
  AND (gs.gs_status IS NULL OR gs.gs_status NOT LIKE 'delayed%')
ON CONFLICT (gs_id) DO NOTHING;

SELECT count(*) FROM production.gwc34_118_gs_count_audit;   -- must equal step 0

-- 2) Apply: set gs_count from the rows that actually exist.
UPDATE production.geneset gs
   SET gs_count = v.real_rows
  FROM gwc34_real_counts v
 WHERE v.gs_id = gs.gs_id
   AND gs.gs_count IS DISTINCT FROM v.real_rows
   AND (gs.gs_status IS NULL OR gs.gs_status NOT LIKE 'delayed%');

-- 3) Verify: this must return zero rows.
SELECT gs.gs_id, gs.gs_count, v.real_rows
FROM production.geneset gs
JOIN gwc34_real_counts v ON v.gs_id = gs.gs_id
WHERE gs.gs_count IS DISTINCT FROM v.real_rows
  AND (gs.gs_status IS NULL OR gs.gs_status NOT LIKE 'delayed%');

COMMIT;

-- Search serves gs_count out of the Sphinx/Manticore index, not the table, so the
-- corrected numbers only reach search results once the index is rebuilt. The search
-- sidecar runs `indexer --all` at pod start, so run this migration BEFORE the
-- environment's deploy and the rollout picks the new values up automatically.
-- Timing on dev: ~18s end to end, 33 rows updated.

------------------------------------------------------------------------------------------------------------------------
-- Rollback
------------------------------------------------------------------------------------------------------------------------
-- BEGIN;
-- UPDATE production.geneset gs
--    SET gs_count = a.prev_gs_count
--   FROM production.gwc34_118_gs_count_audit a
--  WHERE a.gs_id = gs.gs_id;
-- COMMIT;
-- DROP TABLE production.gwc34_118_gs_count_audit;
