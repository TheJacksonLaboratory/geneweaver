------------------------------------------------------------------------------------------------------------------------
-- GWC-44 / G3-776: Binary gene sets are thresholded on upload and become unusable in tools
------------------------------------------------------------------------------------------------------------------------
--
-- Root cause: production.process_thresholds() (run by production.create_geneset2 on
-- every UI upload, and by the geneset_threshold_update trigger on every threshold
-- change) evaluated Binary (gs_threshold_type = 3) as:
--
--     gsv.gsv_value > cast(gs_threshold as numeric)
--
-- With the binary default threshold '1', that is `value > 1`. Binary values are 0/1,
-- so nothing is > 1 and EVERY gene in a binary set was flagged gsv_in_threshold = FALSE.
-- All analysis tools and in-threshold count queries filter on gsv_in_threshold, so the
-- whole set became invisible/unusable -- even a plain all-1 membership list.
--
-- Fix: a binary gene set is a membership list -- every listed gene is a member, so binary
-- sets are NOT thresholded. Mark all of their values in-threshold. This also matches the
-- Python batch/edit paths (batch.BatchReader.__check_thresholds and
-- geneweaverdb.recompute_geneset_value_thresholds), which were fixed the same way.

-- 1) Replace the stored procedure: Binary -> always in-threshold.
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
   -- NOT thresholded -- every listed gene is a member and is in-threshold. Previously
   -- this was `gsv.gsv_value > cast(gsvt.gs_threshold as numeric)`, i.e. `value > 1`
   -- for the default binary threshold, which left every 0/1 value out-of-threshold and
   -- made the whole set unusable in tools.
        WHEN gs_threshold_type=3 THEN
        TRUE

   -- double threshold (gsst = 4 or 5)
        WHEN (gs_threshold_type=4 OR gs_threshold_type=5) THEN
         (ABS(gsv.gsv_value) BETWEEN thresh[1] AND thresh[2])

        WHEN gs_threshold_type=6 THEN
         (gsv.gsv_value BETWEEN thresh[1] AND thresh[2])

        WHEN gs_threshold_type=7 THEN
         (gsv.gsv_value NOT BETWEEN thresh[1] AND thresh[2])

        WHEN gs_threshold_type=8 THEN
         (gsv.gsv_value=thresh[1])
   END;

   RETURN 1;
END$function$;

-- 2) Backfill existing binary gene sets that were incorrectly thresholded so they are
--    usable again (acceptance criterion #3). Every value of a binary set is in-threshold.
UPDATE extsrc.geneset_value gv
SET gsv_in_threshold = TRUE
FROM production.geneset gs
WHERE gv.gs_id = gs.gs_id
  AND gs.gs_threshold_type = 3
  AND gv.gsv_in_threshold IS DISTINCT FROM TRUE;
