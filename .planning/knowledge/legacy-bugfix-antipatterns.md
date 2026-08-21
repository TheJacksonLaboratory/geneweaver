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

---

# Round 3 — GWC-34 upload path, G3-805 homology, docs ownership, PR #2 security review

> Extracted: 2026-08-16
> Source: same branch, commits `0d36c639..77161d1b` (merged as PR #2 on 2026-08-14),
>   plus PR #3 (docs consolidation) and PR #4 (GWC-35 note).

## Failed Patterns (cont.)

### 13. Closing a denormalized-value bug after fixing one writer
- **What was done:** Round 2 fixed `gs_count` in `insert_into_geneset_value_by_gsid()` — the path
  the reproduction exercised — and the ticket was treated as resolved.
- **Failure mode:** That path only runs on curator gene-edits and delayed-upload commits. A plain
  new upload never reaches it, so the reported symptom persisted after the fix shipped: GS407881
  still showed 9 in My Genesets against 4 genes on the geneset page. Two further writers held the
  same fault with *different* wrong formulas — submitted line count (inflated by at least one on
  any file ending in a newline) and a `WHERE ode_pref` join counting one row per preferred
  identifier per gene, roughly doubling it. The latter's `GROUP BY gs_id` also returned no row for
  an empty geneset, so `fetchone()[0]` raised `TypeError`.
- **Evidence:** commit 3ddd38a5, following a133bd2b.
- **How to avoid:** Before closing, grep every assignment to the column. Reproducing one path
  proves that path; it says nothing about the others, and per-path formulas rot independently.

### 14. `INNER JOIN` on an optional mapping table, silently shrinking a set
- **What was done:** Both sides of Find Similar's Jaccard `INNER JOIN`ed `extsrc.homology` and
  counted `DISTINCT hom_id`.
- **Failure mode:** Any in-threshold gene with no homology row vanished from the set. GS407827 has
  8 in-threshold genes; `ode_gene_id` 82243 has no homology row, so Find Similar saw 7 and scored
  0.1250 against the tool's 0.1176. The error is **bidirectional** — inflating where the dropped
  gene sits in one set, deflating where both sets share it — so it cannot be dismissed as a
  consistent bias. 8.6% of in-threshold memberships affected on dev, 8.4% on sqa.
- **Evidence:** commit 5c79bb0d (G3-805, reported via GWC-35). Residual recorded, not hidden:
  255 of 136,211 genes (0.19%) carry more than one `hom_id` and contribute two keys where the tool
  merges them; no sampled pair hit this.
- **How to avoid:** An `INNER JOIN` to an enrichment/mapping table is a filter. Where the mapping is
  optional, `LEFT JOIN` and key on the fallback. Ask what fraction of rows lack the mapping before
  choosing the join type.

### 15. Assuming a backfill is visible once it commits
- **What was done:** Migration 118 corrected `gs_count` in the database; correctness was checked
  by querying the table.
- **Failure mode:** Search still served the old values — `gs_count` is a materialised Sphinx
  attribute (`sql_attr_uint`), not a live read. And a *delta* reindex can never recover them:
  `geneset_delta_src` selects on `gs_updated >= sphinxcounters.last_update`, which the backfill
  intentionally does not touch. Only `indexer --all` republishes. GS407872: 1538 in the DB, 1901
  still served.
- **Evidence:** commit 93ae3aa1, checked against the running dev search sidecar.
- **How to avoid:** For any backfill, identify what caches or indexes the column and whether the
  incremental refresh path can even detect your change. Verify through the surface the user reads.
  (Related trap recorded there: genesets created since the last index build are absent from search
  entirely, so a freshly uploaded test geneset must be verified on My Genesets, not search results.)

### 16. Fixing only the line the reviewer flagged
- **What was done:** Copilot reported stored XSS at `uploadgeneset.html:780`.
- **Failure mode:** The same sink existed in three more places across the two upload templates.
  Upload results echo values from the user's own file and are rendered as markup — the `bsAlerts`
  plugin does `.html(r.message)` and the batch template sets `.html(...)` directly — so a gene
  identifier like `<img src=x onerror=...>` executes when results are shown back. Fixing the
  reported line alone would have closed the ticket and left the vulnerability.
- **Evidence:** commit f11ae9fb; fixed via `gwEscapeHtml`/`gwEscapeHtmlJoin`, escaping through the
  browser's own text-to-HTML conversion rather than a regex, then joining with trusted separators.
- **How to avoid:** Treat a review finding as a class, not an instance. Grep the shape across the
  feature and report what you cleared as well as what you fixed.

### 17. Passing a secret as a URL query parameter
- **What was done:** Both NCBO calls pass the key as `params={'apikey': API_KEY, ...}`, and both
  failure paths logged the caught exception directly.
- **Failure mode:** `requests` embeds the fully prepared URL in its exception message, so `str(e)`
  wrote the API key — and, on the annotator call, the user's submitted text — to pod stdout and
  Cloud Logging. Confirmed present in `str(e)` before the fix and absent after.
- **Evidence:** commit f11ae9fb; `describe_request_error()` now reports type, HTTP status, and the
  bare endpoint (no query string). The key remains hardcoded as a fallback and still needs
  rotating — G3-770, unchanged.
- **How to avoid:** Prefer a header over a query parameter for credentials. Where the API forces a
  query parameter, never log the exception, the URL, or the response object — format a redacted
  description. A secret in a URL leaks through exception text, access logs, and referrers alike.
- **Found by the rule sweep, 2026-08-16 — not previously recorded:** applying the new
  `auto-legacy-bugfix-4` rule across `legacy/**` (not just `legacy/src/`, which is as far as the
  original investigation looked) surfaced a **second copy of the same NCBO key**:
  `legacy/curation-server/ncbo.py:29` hardcodes it with *no* environment override at all, where
  `legacy/src/annotator.py:31` at least reads `GW_NCBO_API_KEY` first. It does not leak the same
  way — that copy sends the key in a POST body and prints a urllib `HTTPError`, whose `str()`
  omits the URL — but it means the **G3-770 rotation is incomplete as scoped**: rotating the key
  without updating `ncbo.py:29` silently breaks the curation server, and that file is a plain
  committed secret regardless. Worth adding to G3-770.

### 17b. Scoping a secret sweep to the directory the bug was found in
- **What was done:** The PR #2 security fix and its verification greps covered `legacy/src/`.
- **Failure mode:** `legacy/curation-server/` holds an independent copy of the same integration —
  and the same credential, in worse shape. A sweep bounded by where you were already looking
  confirms only that you fixed what you had already found.
- **Evidence:** the finding above; three `apikey` param sites exist under `legacy/`, two of which
  were known.
- **How to avoid:** Sweep secrets at the repository root, not the subtree under investigation.
  Legacy trees frequently carry a second, older copy of an integration that no one is thinking about.

### 18. Declaring permissions in a reusable workflow that its caller does not grant
- **What was done:** `_docs-action.yml` declared `contents: write`; the calling `docs-release.yml`
  declared none.
- **Failure mode:** The repo's default `GITHUB_TOKEN` is read-only
  (`default_workflow_permissions: read`) and a called workflow cannot hold more than its caller
  grants, so the grant would have been capped to read and `gh-deploy`'s push to `gh-pages`
  rejected with a 403 — after a green-looking build. The mirror error is equally real: a callee
  requesting more than the caller grants is a hard failure, so pinning the write inside the shared
  action would have broken the build-only PR job.
- **Evidence:** commit e1ac74aa.
- **How to avoid:** Put permission grants on each caller and let the shared workflow inherit.
  Check the repo's default workflow permissions before assuming a declared scope is effective.

### 19. Repointing user-facing links to a site that is not publicly reachable
- **What was done:** The app's Help entry points were moved from the public `geneweaver-docs`
  Pages site to this monorepo's.
- **Failure mode:** The monorepo is internal, so Pages from it is org-only. Shipped to prod as-is,
  every external geneweaver.org user hits a GitHub org login where the documentation used to be.
- **Evidence:** commit 5a712ad8; accepted on dev, captured as release gate B9 (d35f8aec, d2a853a6).
- **How to avoid:** Before repointing a public link, check reachability *as an anonymous user*.
  Repo visibility propagates to Pages, and internal-by-default is easy to miss when you are logged in.

### 20. A test that depends on module collection order
- **What was done:** A new MSET test imported `from tools.MSET import ...`.
- **Failure mode:** `tests/db/test_get_genesets_hom_ids` shims `tools` as a `MagicMock` in
  `sys.modules` so `geneweaverdb` imports without psycopg2. When it collected first, the new test's
  import resolved against that mock — passing in isolation, failing in the suite.
- **Evidence:** commit 5651bbcd; fixed by dropping foreign `tools` entries before importing and
  restoring them afterwards, verified in both orders.
- **How to avoid:** Module-level `sys.modules` mutation is global state that leaks across tests.
  Isolate and restore it, and run a new test both alone and in the full suite before trusting it.

### 21. Carrying a copy-paste defect across during a migration
- **What was done:** `documentation_request.md` was inherited from `geneweaver-docs`.
- **Failure mode:** The original was `feature_request.md` with only the front-matter `name`
  changed — its `about` text and body still asked about feature requests, under a "Documentation
  request" heading. Copying it verbatim would have imported a known defect into the repo that now
  owns the docs, laundered as "migrated content."
- **Evidence:** commit 02a615ea; prompts rewritten to ask which page, what is wrong, what it
  should say.
- **How to avoid:** Migration is the cheapest moment to fix inherited defects — the file is already
  under review. Read what you carry over instead of trusting that it worked before.

### 22. Stating a precondition that is not one
- **What was done:** The migration plan listed archiving `geneweaver-docs` as required before
  merging, to prevent two pipelines fighting over the site.
- **Failure mode:** No such race exists — each repo's `gh-deploy` pushes to its own `gh-pages` and
  serves its own project path, so neither can overwrite the other. The invented precondition would
  have blocked the rollout on an unrelated repo's archival for no reason.
- **Evidence:** commit d2a853a6, point 1 ("This was my error").
- **How to avoid:** Before writing a blocker into a plan, state the mechanism by which the bad
  outcome would occur. If you cannot, it is a preference or a tidiness step, not a precondition.
  (Note the real ordering constraint still exists for *enabling publish on main* — see pattern 24.)

### 23. Docs that tell contributors to use the tooling you just replaced
- **What was done:** `docs/README.md` came across still instructing contributors to clone
  `geneweaver-docs` and install with Poetry.
- **Failure mode:** Anyone following it would work against the retired repo with the wrong package
  manager, and never touch the new pipeline — the documentation actively routes people away from
  the system it documents. This repo uses uv.
- **Evidence:** commit d2a853a6, point 4; rewritten for `uv sync --only-group docs` / `mkdocs
  serve`, and now documents the `exclude_docs` convention and that new pages must be added to the
  nav or the `--strict` build fails.
- **How to avoid:** When a build system or repo moves, the contributor-facing README is part of the
  change. (Same class as the CLAUDE.md guardrail on Poetry → uv leaving a stale Dockerfile.)
