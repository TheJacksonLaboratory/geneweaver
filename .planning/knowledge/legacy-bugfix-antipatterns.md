# Anti-patterns: Legacy bug fixes (GWC-8, GWC-36, GWC-45/50)

> Extracted: 2026-07-13
> Campaign: none (extracted from the `fix/G3-769-legacy-bug-fixes-and-improvements` branch work)

## Failed Patterns

### 1. `requests.get(url, data=params)` for a GET request
- **What was done:** A urllib→requests port kept `data=params` on a GET (`fetch_ncbo_annotations`).
- **Failure mode:** For GET, requests puts `data` in the request *body*, so NCBO received no
  `text`/`apikey`/`ontologies` and returned nothing → silent annotation failure for months.
- **Evidence:** GWC-8; fixed to `params=params` (commit 456d0147).
- **How to avoid:** Use `params=` for GET query strings; `data=`/`json=` are for request bodies.

### 2. Stale exception handling + missing import in the error path
- **What was done:** After the requests port, the code still `except urllib.error.HTTPError`
  (which requests never raises), had no `timeout`, no `raise_for_status()`, and elsewhere called
  `traceback.format_exc()` while `traceback` was never imported.
- **Failure mode:** Non-2xx responses (e.g. NCBO's 404 error dict) fell through to `json.loads`;
  the error handler itself crashed on the missing `traceback`, masking the real cause; a hung
  endpoint could block the request indefinitely.
- **Evidence:** GWC-8; PR #2 Copilot review; fixed in c2be6326 / 519d45a1.
- **How to avoid:** Match exception types to the client library; always set `timeout`; call
  `raise_for_status()`; ensure imports used on the error path exist; never swallow silently.

### 3. Over-claiming root-cause scope before testing the user's actual path
- **What was done:** Claimed "61% of symbols are silently dropped on upload" from reading one
  function (`get_gene_ids_by_spid_type`).
- **Failure mode:** True only for the *batch* path; the UI single-upload uses `create_geneset2`,
  which already resolved aliases (GS407861 stored 10/10). The claim had to be walked back on the tickets.
- **Evidence:** GS407861 test; correction comments on GWC-36 / G3-768.
- **How to avoid:** Qualify a root-cause claim by the exact code path verified; test the path the
  user actually hits before asserting scope/percentages.

### 4. "Verified fixed" from a check at the wrong layer
- **What was done:** Earlier GWC-50 was called fixed from a worker-level check; and GWC-8 looked
  fixed once the default was `ncbo`.
- **Failure mode:** GWC-50 still 500'd in the *web/template* layer; GWC-8 still returned 0
  annotations (the ontology-acronym 404) until an actual deploy + `annotate_text` test.
- **Evidence:** GWC-50 template `.values()[0]`; GWC-8 post-deploy test.
- **How to avoid:** Verify at the layer the user experiences, end-to-end, on the deployed image —
  not just the unit that was edited.

### 5. Shipping a usable credential as a hardcoded fallback
- **What was done:** `API_KEY = os.environ.get('GW_NCBO_API_KEY', '<real key>')` — env-driven but
  still embeds a working key in source (and git history).
- **Failure mode:** Credential exposure; flagged by Copilot. (Kept temporarily to avoid re-breaking
  dev; rotation tracked as G3-770.)
- **How to avoid:** Read secrets from env/secret store; default to empty and provision a cluster
  Secret; never commit a usable key. (See the CLAUDE.md secrets guardrail.)

### 6. Denormalized static caches drift from the DB
- **What was done:** MSET background files / assumptions about which ontologies/symbols exist,
  precomputed and shipped.
- **Failure mode:** Go stale on gene reloads (GWC-45) or when the external service's vocabulary
  changes (GWC-8 acronyms). Reinforces the migration-era finding.
- **How to avoid:** Resolve from the DB / validate against the live service at runtime; treat any
  shipped cache of external state as a staleness liability (V3 TODO in docs/tools/TOOLS_MIGRATION.md).

---

# Round 2 — GWC-34/G3-782, GWC-51/G3-783, release-plan verification

> Extracted: 2026-08-06
> Source: same branch, commits a133bd2b, 3908c1cd, 0d36c639 + cluster investigation

## Failed Patterns (cont.)

### 7. Counting one thing while storing another
- **What was done:** `insert_into_geneset_value_by_gsid()` set `gs_count` from
  `count(*) FROM production.temp_geneset_value` (staged **source rows**), while the INSERT it
  performs stores one row per **distinct `ode_gene_id`** (`GROUP BY gs_id, ode_gene_id`).
- **Failure mode:** Two identifiers resolving to the same gene — an alias plus its official symbol,
  or a repeated symbol — collapse into one stored row but were already counted twice. Search renders
  `gs_count`, the geneset page counts live, so they disagreed (the reported 135 vs 134). Can only
  over-count, never under-count.
- **Evidence:** GWC-34 / G3-782; reproduced on dev (3 staged → 2 stored, `gs_count`=3); fixed a133bd2b.
- **How to avoid:** When a write path both counts and stores, derive the count *from what was
  stored*. Any aggregation in the INSERT (`GROUP BY`, `DISTINCT`, filtering) makes a separately
  computed count a different number by construction.

### 8. A regression test that passes against the broken code
- **What was done:** Asserted that the `gs_count` UPDATE does not mention `temp_geneset_value`.
- **Failure mode:** The pre-fix statement interpolated its count as a literal
  (`set gs_count = 3`), so it never mentioned the staging table either — the test passed against
  the bug it was written to catch. It read as coverage while protecting nothing.
- **Evidence:** first cut of `test_staging_table_is_never_counted`; rewritten to assert no statement
  *anywhere* counts the staging table, then confirmed failing pre-fix.
- **How to avoid:** Run every new assertion against the broken code — `git stash` the fix, or mutate
  the source deliberately. Assert on behaviour or on the whole statement list, not on the text of the
  one statement you happen to be thinking about.

### 9. CI test lists that enumerate modules instead of discovering them
- **What was done:** `_legacy-tests.yml` runs `python -m unittest <explicit module list>`.
- **Failure mode:** A new `tests/test_*.py` passes locally, is never executed by CI, and the PR goes
  green — the exact regression the test was written to prevent ships unguarded.
- **Evidence:** `test_geneset_count_maintenance` required an explicit workflow edit; noted on G3-779.
- **How to avoid:** Prefer discovery. Where a list is unavoidable, treat "add to the runner list" as
  part of adding a test, and confirm the test name appears in the CI log.

### 10. Treating `origin/main..branch` as the release scope
- **What was done:** The release plan described the 1.6.0 scope as "one commit range:
  `origin/main..fix/G3-769-…` (20 commits)".
- **Failure mode:** Understated the release by about half. 21 further `legacy/` commits were already
  merged to `main` via the earlier G3-748 PR and had never reached SQA/Stage/Prod — invisible to that
  range precisely *because* they are merged. They include MSET Python 2→3 fixes, a DBSCAN crash fix,
  and the Auth0 secret-logging fix. The plan's own table already cited two of them, so the document
  contradicted itself.
- **Evidence:** commit 0d36c639; `git log --since=2026-06-01 origin/main -- legacy/`.
- **How to avoid:** Scope a release by *what the target environment currently runs* versus what will
  be deployed — not by the diff of the branch in front of you. Especially where environments are
  served by a different pipeline.

### 11. Fixing and shipping without a tracking ticket
- **What was done:** GWC-51's fix was written, merged to `main` and deployed to dev with no G3
  counterpart created.
- **Failure mode:** It was absent from the G3-769 umbrella and from the G3-781 release plan's
  verification list, so it would have reached SQA/Stage/Prod untracked and unverified — while the
  source ticket sat in "To Do" as if nothing had happened.
- **Evidence:** GWC-51 still `To Do` a month after `0ba54c0a`; G3-783 created retrospectively.
- **How to avoid:** Where a source-project ticket (GWC) drives work planned in another project (G3),
  the counterpart is what carries it into the umbrella and release checklist. No counterpart means
  invisible at release time.

### 12. Assuming a learned quality rule remediates existing violations
- **What was done:** `auto-legacy-monorepo-migration-4` (`|| echo WARN` in Dockerfiles) was recorded
  by an earlier /learn run.
- **Failure mode:** The rule existed for weeks while `legacy/tools-worker/Dockerfile:71` still
  contained the exact pattern. Rules fire on *edits*; they do not fix what is already there, and the
  knowledge base can read as "handled" when the code is unchanged.
- **Evidence:** rule present in `.claude/harness.json`; pattern still present in the Dockerfile
  (verified 2026-08-06). Only the release plan's §4.3.2 assertion actually mitigates it today.
- **How to avoid:** When adding a rule, sweep for existing violations and either fix them or record
  them explicitly as accepted. A rule is a ratchet, not a repair.
