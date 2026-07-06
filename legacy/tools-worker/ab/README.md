# Tool A/B harness (dev vs sqa)

Runs a legacy GeneWeaver analysis tool with the **same geneset inputs** in the
`dev` and `sqa` environments and diffs the results, so you can confirm both
return equivalent output. It dispatches the real Celery task the same way the
web blueprints do (insert a `production.result` row → `celery.send_task` with
`gsids`/`output_prefix`/`params`), waits for completion, and compares.

## Why the diff is "smart"
dev's gene reload remapped internal `ode_gene_id`s, so raw output differs by
design. The comparator canonicalizes before diffing: it drops the run uuid /
URLs / output_prefix, compares gene-/node-/edge-lists **by length** (the count
is the signal, not the remapped IDs), and rounds floats. What remains are the
meaningful numbers — jaccard values, p-values, overlap counts, set sizes.

## Usage
From a machine with `kubectl` pointed at `jax-cluster-dev-10` (namespaces
`dev` + `sqa`):

```bash
python3 ab_compare.py <ToolClassname> <gsid,gsid,...> [params_json] [timeout_s]

# examples (use genesets that exist in BOTH envs):
python3 ab_compare.py JaccardSimilarity 396123,390337,392374
python3 ab_compare.py GeneSetViewer    396123,390337,392374
python3 ab_compare.py BooleanAlgebra   396123,390337,392374 '{"BooleanAlgebra_Relation":"Union","at_least":"2"}'
```

It prints a per-field diff (or `✅ MATCH`) and writes the raw outputs to
`/tmp/ab_out/<Tool>_dev.json` and `_sqa.json` for manual inspection.

## Files
- `run_tool_in_env.py` — runs **inside** a `geneweaver-legacy-tools` pod
  (auto-detects the tools dir: `/app/tools-worker` on dev, `/app/src` on sqa),
  dispatches one task, polls, prints the result JSON between sentinels.
- `ab_compare.py` — orchestrator: `kubectl cp`s the runner into both pods,
  runs it in each, canonicalizes + diffs.

## Notes / gotchas
- **Per-tool params:** defaults come from `odestatic.tool_param`. Some tools
  need extra keys the web form adds (e.g. BooleanAlgebra needs `at_least`).
  Pass them as the `params_json` arg.
- **Active tools:** ABBA, BooleanAlgebra, Combine, DBSCAN, GeneSetViewer,
  JaccardClustering, JaccardSimilarity, MSET, PhenomeMap. (Others are inactive.)
- **sqa worker can wedge** after redis blips (connected but not consuming). If
  tasks pile up unconsumed: `kubectl rollout restart deploy/geneweaver-legacy-tools -n sqa`.
- Each run inserts a `production.result` row tagged `res_description='AB-test: …'`
  in both DBs; clean up with
  `DELETE FROM production.result WHERE res_description LIKE 'AB-test:%';`.
- **Known finding:** JaccardSimilarity p-values differ (dev computes real
  significance from the backfilled `extsrc.jaccard_distribution_results`; sqa
  returns `p = 0`). Jaccard values & overlap counts match.

## Success guard (important)
A `MATCH` is only reported when **both** runs actually succeeded — otherwise two
identical *failures* would look like a match. A run counts as success only if
Celery returned `SUCCESS`, the tool did not log `ERROR` into `res_status`, **and**
the result payload has no embedded `error`. Legacy tools return Celery `SUCCESS`
even when the task body catches an exception: most write `ERROR - ...` into
`res_status`, but some (e.g. **MSET**) instead stash the failure in
`res_data['error']` and still finish as `DONE` — so a status-only check would
miss it. If either side fails, the harness prints `❌ FAILED` for that env and
`⛔ INVALID COMPARISON` (and exits non-zero) instead of a verdict.

Corollary: some tools need real parameters, not `{}`. E.g. **MSET** requires a
blueprint-built `gs_dict` (two same-species non-microarray genesets + gene
symbols + a background file) — running it with `{}` fails on both sides and is
(correctly) reported as an invalid comparison, not a match.
