------------------------------------------------------------------------------------------------------------------------
-- G3-809 item 3: the P-Value / Q-Value boundary (score types 1 & 2) is exclusive in the DB
--                proc and inclusive in both Python paths
------------------------------------------------------------------------------------------------------------------------
--
-- Raised in review of PR #12, and the third face of the same bug migrations 117 and 119
-- addressed for other score types: gsv_in_threshold -- the column every analysis tool and
-- in-threshold count filters on -- is written for score types 1 and 2 by two different rules:
--
--   * production.process_thresholds (the DB proc, run by create_geneset2 on UI upload and by
--     the geneset_threshold_update trigger on every threshold change):
--         gsv_value <  threshold        (EXCLUSIVE)
--   * geneweaverdb.recompute_geneset_value_thresholds (score-type edit) and
--     batch.BatchReader.__check_thresholds (batch upload):
--         gsv_value <= threshold        (INCLUSIVE)
--
-- So a p-value of exactly 0.05 in a `P-Value < 0.05` set is a member or not depending on
-- which path last wrote the row. Migrations 117 and 119 both carried the exclusive form
-- forward unchanged, so converging the writers needs this third step.
--
-- Which is correct: INCLUSIVE (`<=`). This is settled by the repo, not a judgement call --
-- the v3 reimplementation states the rule explicitly and tests it at the boundary:
--
--   * packages/core .../parse/threshold.py -- `one_sided_threshold()` (the function
--     check_threshold() dispatches P_VALUE and Q_VALUE to) is `return value <= threshold`,
--     and its docstring spells it out: "if the threshold is 0.05, then this function will
--     return True if the value is less than or equal to 0.05".
--   * packages/core tests .../threshold/test_one_sided_threshold.py enumerates the boundary
--     DELIBERATELY, three times, each with a comment:
--         (0.05, 0.05, True)   # Test case where value is equal to threshold
--         (0.0,  0.0,  True)   # Test case where value is equal to zero threshold
--         (-0.1, -0.1, True)   # Test case where value is equal to negative threshold
--   * legacy geneweaverdb.recompute_geneset_value_thresholds -- `gsv_value<=%s`, docstring
--     "P-Value / Q-Value: in-threshold when value <= threshold".
--   * legacy batch.BatchReader.__check_thresholds -- `value <= threshold`, asserted
--     boundary-inclusive in legacy/tests/test_batch_thresholds.py.
--
-- Inclusive is also the house rule for the two-sided score types everywhere (BETWEEN in this
-- proc and in packages/db; `threshold_low <= value <= threshold` in packages/core), so the
-- one-sided strict `<` is the odd one out in both codebases rather than a considered choice.
--
-- The user-facing batch syntax is written `P-Value < 0.05`, which reads exclusive, and that is
-- the only thing on the other side. It is a label for the score type, not an operator spec,
-- and it is outweighed by an explicitly documented and boundary-tested implementation. Worth a
-- heads-up to curation before Stage/Prod because it moves membership in ~600 published gene
-- sets per environment -- but as a notification, not a decision to be made.
--
-- ⚠ SAME BUG EXISTS IN v3: packages/db .../query/threshold.py builds the one-sided branch as
-- `WHEN gsv_value < %(threshold_high)s THEN TRUE` -- exclusive, contradicting packages/core in
-- the same repo. Its test asserts only that the SQL contains `%(threshold_high)s`, `WHEN`,
-- `THEN TRUE` etc., never the operator, so the `<` is unasserted rather than intended. Fixing
-- it there is out of scope for this legacy migration but must not be forgotten, or v3 will
-- reintroduce exactly the divergence this migration removes.
--
------------------------------------------------------------------------------------------------------------------------
-- SCOPE  -- read before running
------------------------------------------------------------------------------------------------------------------------
--
-- Affects only score types 1 and 2 whose stored threshold is a well-formed single numeric,
-- and within those only rows whose value is EXACTLY equal to the cutoff. Those flip
-- FALSE -> TRUE (they become members); every other type-1/2 row keeps the membership it has.
-- Types 3-8 are untouched.
--
-- Measured 2026-09-03, read-only, against the live databases:
--
--     geneweaver-dev :  14,431 rows across   590 gene sets
--     geneweaver-sqa :  28,205 rows across   601 gene sets
--
-- In both, the flipping rows are exactly the rows sitting on the cutoff (rows_to_change ==
-- count(gsv_value = cutoff)), which is the intended population and a useful sanity check.
-- This is NOT a handful of rows -- it is more gene sets than migration 119 touched (431 on
-- sqa) -- so it gets its own audit and its own approval. Stage and Prod are unmeasured from
-- here (RBAC denies access); run step 0 there first and batch by gs_id if it is much larger.
--
-- gsv_in_threshold is NOT a materialised search attribute (unlike gs_count in 118), so this
-- needs no reindex: the tools read it live from extsrc.geneset_value and the corrected
-- membership takes effect on commit. gs_count counts all value rows regardless of threshold,
-- so search counts do not move either.
--
-- Idempotent? Yes -- the backfill only rewrites rows that currently disagree, and the proc
-- replace is CREATE OR REPLACE; a second run matches nothing. Reversible? Yes, via the audit
-- table captured in step 1 plus the proc rollback at the foot -- read that section, it has
-- the same quiesced-vs-resumed caveat as 119.
--
-- Ordering: run AFTER migration 119. This proc body is 119's with the single type-1/2 line
-- changed, so applying it out of order would silently revert 119's Correlation/Effect fix.
--   * dev and sqa already have 119 applied (verified 2026-09-03: no ABS( in the live proc,
--     type-4/5 reads signed BETWEEN, 119 audit present and its backfill complete) -- they
--     need only this migration.
--   * Stage and Prod have neither: apply 119 first, then this.
--
-- Cost: one pass over the type-1/2 rows of extsrc.geneset_value, which is the largest score
-- type -- expect this to be slower than 119. Materialised once below.

BEGIN;

-- Parse each well-formed type-1/2 cutoff once: a single numeric, not a range. The regex is
-- the single-value form of 119's, so it accepts everything the proc's
-- cast(gs_threshold as numeric) accepts and skips only a non-numeric or empty threshold
-- (which would error the proc per-geneset anyway).
CREATE TEMP TABLE g3809_t12 ON COMMIT DROP AS
SELECT gs.gs_id,
       gs.gs_threshold::numeric AS cutoff
FROM production.geneset gs
WHERE gs.gs_threshold_type IN (1, 2)
  AND gs.gs_threshold ~ '^\s*[-+]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?\s*$';

CREATE UNIQUE INDEX ON g3809_t12 (gs_id);
ANALYZE g3809_t12;

-- 0) Size it: rows whose membership flips when the cutoff becomes inclusive. The second
--    column is the cross-check -- it must equal the first, since only rows sitting exactly
--    on the cutoff can change.
SELECT count(*)                                              AS rows_to_change,
       count(*) FILTER (WHERE gv.gsv_value = t.cutoff)        AS rows_exactly_on_cutoff,
       count(DISTINCT gv.gs_id)                               AS sets_affected
FROM extsrc.geneset_value gv
JOIN g3809_t12 t ON t.gs_id = gv.gs_id
WHERE gv.gsv_in_threshold IS DISTINCT FROM COALESCE(gv.gsv_value <= t.cutoff, FALSE);

-- 1) Capture the pre-state so the backfill can be undone (do this in every environment).
--    Not a TEMP table -- it must outlive the transaction to be useful for rollback.
CREATE TABLE IF NOT EXISTS production.g3809_120_pq_boundary_audit (
    gs_id             bigint,
    ode_gene_id       bigint,
    prev_in_threshold boolean,
    new_in_threshold  boolean,
    captured_at       timestamptz,
    PRIMARY KEY (gs_id, ode_gene_id)
);

INSERT INTO production.g3809_120_pq_boundary_audit
    (gs_id, ode_gene_id, prev_in_threshold, new_in_threshold, captured_at)
SELECT gv.gs_id, gv.ode_gene_id, gv.gsv_in_threshold,
       COALESCE(gv.gsv_value <= t.cutoff, FALSE), now()
FROM extsrc.geneset_value gv
JOIN g3809_t12 t ON t.gs_id = gv.gs_id
WHERE gv.gsv_in_threshold IS DISTINCT FROM COALESCE(gv.gsv_value <= t.cutoff, FALSE)
ON CONFLICT (gs_id, ode_gene_id) DO NOTHING;

SELECT count(*) FROM production.g3809_120_pq_boundary_audit;   -- must equal step 0's rows_to_change

-- 2a) Replace the stored procedure: the type-1/2 branch becomes inclusive. The body is
--     migration 119's with that one line changed, so it preserves 117's binary/type-3 fix
--     and 119's signed Correlation/Effect fix. Applying this BEFORE 119 would revert the
--     latter -- see Ordering in the header.
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
        gsv.gsv_value<=cast(gsvt.gs_threshold as numeric)

   -- p-value / q-value (G3-809 item 3): INCLUSIVE of the cutoff. Was a strict `<` in 117
   -- and 119, while recompute_geneset_value_thresholds (`gsv_value<=%s`) and
   -- batch.__check_thresholds (`value <= threshold`) are both inclusive -- so a value
   -- exactly on the cutoff was a member or not depending on which writer last ran.

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

-- 2b) Backfill existing type-1/2 sets to the inclusive cutoff (only rows that differ).
UPDATE extsrc.geneset_value gv
   SET gsv_in_threshold = COALESCE(gv.gsv_value <= t.cutoff, FALSE)
  FROM g3809_t12 t
 WHERE gv.gs_id = t.gs_id
   AND gv.gsv_in_threshold IS DISTINCT FROM COALESCE(gv.gsv_value <= t.cutoff, FALSE);

-- 3) Verify: this must return zero rows.
SELECT count(*) AS should_be_zero
FROM extsrc.geneset_value gv
JOIN g3809_t12 t ON t.gs_id = gv.gs_id
WHERE gv.gsv_in_threshold IS DISTINCT FROM COALESCE(gv.gsv_value <= t.cutoff, FALSE);

COMMIT;

------------------------------------------------------------------------------------------------------------------------
-- Rollback
------------------------------------------------------------------------------------------------------------------------
--
-- Same caveat as migration 119: the audit table is a snapshot of the rows that differed AT
-- MIGRATION TIME. A type-1/2 set created or edited afterwards is not in it, and an audited
-- set whose threshold changed afterwards has been legitimately recomputed since, so its
-- captured value is stale. Restore the proc FIRST in both paths.
--
-- Step 1 (both paths) -- restore the exclusive proc: re-run migration 119, whose body is
--   identical apart from the type-1/2 line. Do NOT re-run 117 for this: that would also
--   revert 119's Correlation/Effect fix.
--
-- Path A -- IMMEDIATE rollback, writes quiesced. Guarded so it only restores rows still
--   holding what this migration wrote, and reports any that have moved since:
--
-- BEGIN;
-- SELECT count(*) AS changed_since_migration
--   FROM production.g3809_120_pq_boundary_audit a
--   JOIN extsrc.geneset_value gv
--     ON gv.gs_id = a.gs_id AND gv.ode_gene_id = a.ode_gene_id
--  WHERE gv.gsv_in_threshold IS DISTINCT FROM a.new_in_threshold;
--
-- UPDATE extsrc.geneset_value gv
--    SET gsv_in_threshold = a.prev_in_threshold
--   FROM production.g3809_120_pq_boundary_audit a
--  WHERE gv.gs_id = a.gs_id AND gv.ode_gene_id = a.ode_gene_id
--    AND gv.gsv_in_threshold IS NOT DISTINCT FROM a.new_in_threshold;
-- COMMIT;
-- DROP TABLE production.g3809_120_pq_boundary_audit;
--
-- Path B -- rollback AFTER writes resumed. Recompute rather than restore; once step 1 has
--   put the exclusive proc back, the proc is the definition of the old rule:
--
-- BEGIN;
-- DO $$
-- DECLARE r record;
-- BEGIN
--   FOR r IN SELECT gs_id FROM production.geneset
--             WHERE gs_threshold_type IN (1,2)
--               AND gs_status <> 'deleted'
--               AND gs_threshold <> ''
--   LOOP
--     PERFORM production.process_thresholds(r.gs_id);
--   END LOOP;
-- END $$;
-- COMMIT;
-- DROP TABLE production.g3809_120_pq_boundary_audit;
--
--   Batch this on prod -- it is one proc call per gene set, and types 1/2 are the bulk of
--   the corpus.
