------------------------------------------------------------------------------------------------------------------------
-- G3-809: Correlation/Effect (score types 4 & 5) membership uses ABS(value) in the DB
--         proc but the signed value everywhere else
------------------------------------------------------------------------------------------------------------------------
--
-- gsv_in_threshold -- the column every analysis tool and in-threshold count filters on --
-- is written for score types 4 (Correlation) and 5 (Effect) by two different rules:
--
--   * production.process_thresholds (the DB proc, run by create_geneset2 on UI upload and
--     by the geneset_threshold_update trigger on every threshold change):
--         ABS(gsv_value) BETWEEN thresh[1] AND thresh[2]
--   * geneweaverdb.recompute_geneset_value_thresholds (score-type edit) and
--     batch.BatchReader.__check_thresholds (batch upload):
--         gsv_value BETWEEN thresh[1] AND thresh[2]
--
-- So the same geneset gets different membership depending on which path last ran. This is
-- G3-809 item 2. (Item 1 -- the tool-output routes' hardcoded [-1,1] rule -- is fixed in
-- code; those routes now go through recompute_geneset_value_thresholds.)
--
-- Which is correct: the SIGNED value (no ABS). GeneWeaver documents the threshold to users
-- as a plain range on the value -- the batch score-type syntax is `! 0.40 < Correlation <
-- 0.90` and `! 6.0 < Effect < 22.50` (batchupload.html), the upload/edit help says
-- "Correlation/Effect: min,max (e.g. -1,1)" (editgenesets.html), the batch validator parses
-- `<lower> < correlation < <upper>`, and both Python implementations already use plain
-- BETWEEN. ABS only diverges for ASYMMETRIC ranges, and there it is wrong twice over: for
-- `6.0 < Effect < 22.50` it silently also admits the -22.50..-6.0 band the user never asked
-- for, and for an auto-derived type-5 set (threshold stored as the data's own `min,max`) it
-- excludes the most-negative genes that DEFINED the minimum. Effect scores (log fold-change,
-- effect size) are inherently signed, so magnitude-only membership is simply the wrong model.
--
-- This aligns the DB proc with the documented semantics and the two Python paths, and
-- backfills the existing rows so a threshold change (which fires the trigger) no longer flips
-- membership. Symmetric ranges (e.g. `-1,1`) are unaffected -- ABS and signed agree there.
--
------------------------------------------------------------------------------------------------------------------------
-- SCOPE  -- read before running
------------------------------------------------------------------------------------------------------------------------
--
-- Affects only score types 4 and 5 whose stored threshold is a well-formed `low,high` range;
-- rows where signed membership differs from ABS membership. Measured on geneweaver-sqa
-- (2026-09-01): 431 gene sets (424 gs_status 'normal'), 111,561 of 3,632,817 type-4/5 value
-- rows flip. Symmetric-range and type 1/2/3/6/7/8 sets are untouched. The only type-4/5 sets
-- the range filter excludes on SQA are 3 with an empty ('') threshold -- no threshold set --
-- which are a separate malformed-data case (the proc reads all such rows out-of-threshold
-- while the Python recompute reads them all in; not reconciled here).
--
-- gsv_in_threshold is NOT a materialised search attribute (unlike gs_count in migration 118),
-- so this needs no reindex: the analysis tools read it live from extsrc.geneset_value, and
-- the corrected membership takes effect the moment this commits. gs_count is a count of all
-- value rows regardless of threshold, so search counts do not move either.
--
-- Idempotent? Yes -- the backfill only rewrites rows that currently disagree, and the proc
-- replace is CREATE OR REPLACE; a second run matches nothing. Reversible? Yes, via the audit
-- table captured in step 1 (per-row prev value) plus the proc rollback at the foot.
--
-- Ordering: run after migration 117 (this reproduces 117's binary/type-3 fix in the proc body
-- below, so it is self-sufficient, but the numbered sequence still applies). No deploy-order
-- coupling like 117/118 -- the change is live on commit.
--
-- Cost: one pass over the type-4/5 rows of extsrc.geneset_value. Materialised once below.

BEGIN;

-- Parse each well-formed type-4/5 range once. The regex matches the PostgreSQL numeric
-- literal grammar (optional sign, decimals with a leading or trailing dot, scientific
-- notation) so it covers every threshold the proc's string_to_array(...)::numeric[] can
-- cast -- e.g. '6.76e-05,0.011', '.5,1.1', '1,15.', '-1.42,+3.03'. A stricter regex would
-- silently skip those and leave them stale. The only thing excluded is a non-numeric
-- threshold (an empty string), which would error the proc per-geneset anyway.
CREATE TEMP TABLE g3809_t45 ON COMMIT DROP AS
SELECT gs.gs_id,
       (string_to_array(gs.gs_threshold, ',')::numeric[])[1] AS lo,
       (string_to_array(gs.gs_threshold, ',')::numeric[])[2] AS hi
FROM production.geneset gs
WHERE gs.gs_threshold_type IN (4, 5)
  AND gs.gs_threshold ~ '^\s*[-+]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?\s*,\s*[-+]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?\s*$';

CREATE UNIQUE INDEX ON g3809_t45 (gs_id);
ANALYZE g3809_t45;

-- 0) Size it: rows whose membership flips when ABS is dropped.
SELECT count(*)                            AS rows_to_change,
       count(DISTINCT gv.gs_id)            AS sets_affected
FROM extsrc.geneset_value gv
JOIN g3809_t45 t ON t.gs_id = gv.gs_id
WHERE gv.gsv_in_threshold IS DISTINCT FROM COALESCE(gv.gsv_value BETWEEN t.lo AND t.hi, FALSE);

-- 1) Capture the pre-state so the backfill can be undone (do this in every environment).
--    Not a TEMP table -- it must outlive the transaction to be useful for rollback.
CREATE TABLE IF NOT EXISTS production.g3809_119_threshold_abs_audit (
    gs_id             bigint,
    ode_gene_id       bigint,
    prev_in_threshold boolean,
    new_in_threshold  boolean,
    captured_at       timestamptz,
    PRIMARY KEY (gs_id, ode_gene_id)
);

INSERT INTO production.g3809_119_threshold_abs_audit
    (gs_id, ode_gene_id, prev_in_threshold, new_in_threshold, captured_at)
SELECT gv.gs_id, gv.ode_gene_id, gv.gsv_in_threshold,
       COALESCE(gv.gsv_value BETWEEN t.lo AND t.hi, FALSE), now()
FROM extsrc.geneset_value gv
JOIN g3809_t45 t ON t.gs_id = gv.gs_id
WHERE gv.gsv_in_threshold IS DISTINCT FROM COALESCE(gv.gsv_value BETWEEN t.lo AND t.hi, FALSE)
ON CONFLICT (gs_id, ode_gene_id) DO NOTHING;

SELECT count(*) FROM production.g3809_119_threshold_abs_audit;   -- must equal step 0's rows_to_change

-- 2a) Replace the stored procedure: Correlation/Effect uses the SIGNED value, not ABS.
--     Body is migration 117's (binary/type-3 -> always in-threshold) with the single
--     type-4/5 line changed from the absolute-value form to `gsv.gsv_value BETWEEN ...`.
--     The proc body deliberately carries no mention of the old form, so that a check like
--     `pg_get_functiondef(...) LIKE '%ABS%'` reliably reports whether this fix is applied.
CREATE OR REPLACE FUNCTION production.process_thresholds(param_gs_id bigint)
 RETURNS information_schema.cardinal_number
 LANGUAGE plpgsql
AS $function$DECLARE
BEGIN

   -- thresholds default to false
   UPDATE geneset_value SET gsv_in_threshold=FALSE WHERE gs_id=param_gs_id;

   UPDATE geneset_value SET gsv_in_threshold=TRUE
   FROM geneset_value gsv,
      (SELECT *, string_to_array( gs.gs_threshold,',')::numeric[] as thresh
       FROM geneset_value gsv NATURAL JOIN geneset gs
       WHERE gs.gs_id=param_gs_id) gsvt
   WHERE gsvt.gs_id=param_gs_id AND
   geneset_value.gs_id=gsv.gs_id AND geneset_value.ode_gene_id = gsv.ode_gene_id AND
   gsv.gs_id = gsvt.gs_id AND gsv.ode_gene_id = gsvt.ode_gene_id AND
   -- return true when in thresholds
   CASE WHEN (gs_threshold_type=1 OR gs_threshold_type=2) THEN
        gsv.gsv_value<cast(gsvt.gs_threshold as numeric)

   -- binary thresholds (GWC-44): a binary gene set is a membership list, so it is
   -- NOT thresholded -- every listed gene is a member and is in-threshold.
        WHEN gs_threshold_type=3 THEN
        TRUE

   -- correlation / effect (G3-809): membership is the SIGNED value within the declared
   -- [min,max] range, matching batch.__check_thresholds, recompute_geneset_value_thresholds
   -- and GeneWeaver's documented `low < Correlation/Effect < high` syntax. (See this
   -- migration's header for why the previous absolute-value form was wrong.)
        WHEN (gs_threshold_type=4 OR gs_threshold_type=5) THEN
         (gsv.gsv_value BETWEEN thresh[1] AND thresh[2])

        WHEN gs_threshold_type=6 THEN
         (gsv.gsv_value BETWEEN thresh[1] AND thresh[2])

        WHEN gs_threshold_type=7 THEN
         (gsv.gsv_value NOT BETWEEN thresh[1] AND thresh[2])

        WHEN gs_threshold_type=8 THEN
         (gsv.gsv_value=thresh[1])
   END;

   RETURN 1;
END$function$;

-- 2b) Backfill existing type-4/5 sets to the signed-value rule (only rows that differ).
UPDATE extsrc.geneset_value gv
   SET gsv_in_threshold = COALESCE(gv.gsv_value BETWEEN t.lo AND t.hi, FALSE)
  FROM g3809_t45 t
 WHERE gv.gs_id = t.gs_id
   AND gv.gsv_in_threshold IS DISTINCT FROM COALESCE(gv.gsv_value BETWEEN t.lo AND t.hi, FALSE);

-- 3) Verify: this must return zero rows.
SELECT count(*) AS should_be_zero
FROM extsrc.geneset_value gv
JOIN g3809_t45 t ON t.gs_id = gv.gs_id
WHERE gv.gsv_in_threshold IS DISTINCT FROM COALESCE(gv.gsv_value BETWEEN t.lo AND t.hi, FALSE);

COMMIT;

------------------------------------------------------------------------------------------------------------------------
-- Rollback
------------------------------------------------------------------------------------------------------------------------
-- 1) Restore membership from the audit table:
-- BEGIN;
-- UPDATE extsrc.geneset_value gv
--    SET gsv_in_threshold = a.prev_in_threshold
--   FROM production.g3809_119_threshold_abs_audit a
--  WHERE gv.gs_id = a.gs_id AND gv.ode_gene_id = a.ode_gene_id;
-- COMMIT;
-- DROP TABLE production.g3809_119_threshold_abs_audit;
--
-- 2) Restore the ABS form of the proc: re-run migration 117 (its type-4/5 branch is the
--    ABS version). 117 is the correct rollback target because it also carries the
--    binary/type-3 fix this migration preserves.
