# Patterns: Legacy bug fixes (GWC-8, GWC-36, GWC-45/50, GWC-49 research)

> Extracted: 2026-07-13
> Campaign: none (no formal campaign file) — extracted from the completed
>   `fix/G3-769-legacy-bug-fixes-and-improvements` branch work + Jira GWC-8/36/45/50/49
> Postmortem: none

## Successful Patterns

### 1. Probe external services for liveness before blaming code vs. service
- **Description:** For a "feature stopped working" bug that calls an external API, hit the
  endpoint (and DNS-resolve the host) from *inside the cluster* before touching code. GWC-8:
  Monarch's SciGraph host `scigraph-ontology.monarchinitiative.org` returned **NXDOMAIN**
  (decommissioned) while NCBO (`data.bioontology.org`) returned HTTP 200 — instantly separating
  "dead dependency" from "our bug."
- **Evidence:** GWC-8 root-cause; `requests.get` + `socket.getaddrinfo` from the pod.
- **Applies when:** any tool/integration that "used to work" and calls a third-party endpoint.

### 2. Ground-truth in the DB before trusting the ticket's hypothesis
- **Description:** GWC-36 was reported as "lncRNAs aren't in the DB." DB queries showed those
  genes ARE present (as *preferred* symbols); the real cause was `ode_pref='t'`-only matching
  dropping *alias* symbols. Quantified it: 65,019/105,975 (61.4%) human symbols are alias-only.
- **Evidence:** `extsrc.gene` queries against dev; GS407861 stored-genes check.
- **Applies when:** a bug is attributed to "missing data" — verify presence + the exact query path.

### 3. Distinguish code paths empirically before claiming scope
- **Description:** The same user symptom had two paths: UI single-upload → `create_geneset2`
  stored proc (already resolved aliases) vs. batch upload → `get_gene_ids_by_spid_type`
  (dropped aliases). Testing GS407861 corrected an over-broad "genes are dropped" claim.
- **Evidence:** GS407861 = 10/10 stored; the "not present" text was a stale case-sensitive warning.
- **Applies when:** multiple code paths can produce one symptom — verify the path the user hits.

### 4. Fast pod-level verification of a deployed legacy fix
- **Description:** Confirm the deployed image tag, then `kubectl exec` the pod and import the
  module + call the function directly (`geneweaverdb.get_gene_ids_by_spid_type`,
  `annotator.annotate_text`) to verify behavior on the live image without a full UI round-trip.
- **Evidence:** verified image `356fb76`; resolver len 105,975; annotate_text returned 24 terms.
- **Applies when:** validating a legacy fix on dev before/after redeploy.

### 5. "Prefer preferred, else fall back" for identifier resolution
- **Description:** Resolve gene symbols including non-preferred aliases, but let the preferred row
  win on collision — implemented in SQL with `DISTINCT ON (lower(ode_ref_id)) ... ORDER BY
  lower(ode_ref_id), ode_pref DESC` (Copilot-suggested improvement over Python dict-overwrite).
  Preserves the Ccr4/Cnot6 disambiguation while recovering alias-only genes. Verified equivalent.
- **Evidence:** GWC-36 fix + PR #2 review; matches v3 `db.query.gene.mapping()`.
- **Applies when:** mapping user-supplied identifiers to internal IDs where aliases + collisions coexist.

### 6. Layered "restore a broken feature" — don't stop at the first root cause
- **Description:** GWC-8 needed four independent fixes, each surfaced by the next test:
  `data=`→`params=`, add `import traceback`, default `monarch`→`ncbo`, and (found only after
  deploy) filter the ontology list to NCBO-supported acronyms (NCBO 404s the whole request on
  one unknown acronym). Each dev test revealed the next layer.
- **Evidence:** GWC-8 commits 456d0147 → c2be6326.
- **Applies when:** a long-dead feature — expect multiple stacked defects; verify end-to-end each round.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fix GWC-8 & GWC-36 in legacy, not v3 | v3 has no annotator and only a stub upload; prod is affected now and legacy still serves prod | Fixed + verified on dev; prod pending standalone pipeline |
| Route GWC-49 (Search Threshold) to v3 | Legacy Sphinx can't filter genesets by the searched gene's per-gene value; v3 already has ScoreType/threshold/search scaffolding | Story G3-764 under epic G3-763 |
| Keep the NCBO API-key fallback; defer removal | Defaulting to empty would re-break dev annotation until `GW_NCBO_API_KEY` is a cluster secret | Documented + tracked as G3-770 (mirrors Auth0 G3-761) |
| Group legacy fixes via issue links, not parent | Jira hierarchy forbids Bug-under-Story; only Sub-tasks nest under Story | Umbrella story G3-769 with Relates links |
| DISTINCT ON over Python dedup (Copilot) | De-dup in SQL, one row/symbol, deterministic; less data over the wire | Adopted; verified equivalent on dev |

---

# Round 2 — GWC-34/G3-782, GWC-51/G3-783, release-plan verification

> Extracted: 2026-08-06
> Source: same branch (`fix/G3-769-legacy-bug-fixes-and-improvements`), commits
>   a133bd2b, 3908c1cd, 0d36c639 + dev/sqa/prod cluster investigation
> Postmortem: none

## Successful Patterns (cont.)

### 7. Disprove your own root-cause hypothesis against data before building on it
- **Description:** A hypothesis derived purely from reading code looked airtight (GWC-34: the
  `ode_pref` join in `genesetblueprint.py:508` double-counting genes with preferred refs in several
  ID sources). Replaying that exact expression against every drifted geneset matched the stored
  value **0 times** on dev *and* sqa. A second hypothesis (stale Sphinx index) also died on
  inspection — search re-queries the DB per hit (`get_geneset_no_user`) and uses the indexed
  `gs_count` only for filtering/sorting. Only the third survived.
- **Evidence:** `cause_confirmed=0` of 139 (dev) and of the sqa sample; `search.py:606-611`.
- **Applies when:** any root cause inferred from reading code. Write the query that would
  *falsify* it, not the one that would confirm it — and do it before filing the fix.

### 8. When data forensics comes up empty, reproduce with the real function
- **Description:** No amount of querying found GWC-34, because the buggy path never ran on the
  databases being queried. The decisive step was constructing the trigger condition: create a
  throwaway geneset, stage 3 source rows resolving to 2 distinct genes, call the real
  `insert_into_geneset_value_by_gsid()`, observe `gs_count=3` vs `count(*)=2`. Cleanup in a
  `finally`, verified afterwards.
- **Evidence:** dev reproduction 2026-08-05; both throwaway genesets + `file` rows removed, `(0,0,0)`.
- **Applies when:** the symptom is real but queries show clean data. Exercise the code, don't
  interrogate its output.

### 9. Read "clean in non-prod" as "this path never runs here"
- **Description:** dev and sqa showed **zero** `gs_count` drift among populated genesets (5,000
  sampled each), which initially read as "no bug". The path that causes it only runs on curator
  gene-edits and delayed-upload commits — prod traffic. Bulk-loaded environments never exercise it.
- **Evidence:** dev 80/5,000 drifted, all empty genesets; sqa 77/5,000, same shape; 0 with genes.
- **Applies when:** a prod-reported bug won't reproduce in lower environments. Ask which traffic
  those environments *don't* receive before concluding it's fixed, environmental, or imaginary.

### 10. Mutation-test every new regression assertion
- **Description:** Confirm each test fails against broken code, not just passes against good code.
  Done three ways here: `git stash` the fix (2 failures), interpolate `gsid` (fails *only* the
  binding test), drop the subquery `WHERE` (fails *only* the scoping test).
- **Evidence:** commit 3908c1cd; the first cut of `staging_table_is_never_counted` **passed**
  against pre-fix code — the buggy statement interpolated its count as a literal and so never
  mentioned the staging table. It looked like coverage and was worthless.
- **Applies when:** adding any regression test. A test that cannot fail is worse than no test,
  because it reads as coverage.

### 11. Confirm the CI gate actually executes the new test
- **Description:** `.github/workflows/_legacy-tests.yml` enumerates test modules explicitly rather
  than discovering them. A new `tests/test_*.py` passes locally and is silently skipped by CI.
- **Evidence:** `test_geneset_count_maintenance` had to be added to the list; verified in run
  `30919259942` ("Ran 48 tests") that it actually executed.
- **Applies when:** adding a test file to any suite — check the runner's selection mechanism, and
  verify the new test's name in the CI log rather than trusting a green tick.

### 12. Verify planning-document claims against the live system
- **Description:** Three claims in the G3-781 release plan were checkable in minutes and wrong or
  incomplete: §4.3.1's "biggest unknown" (all four namespaces already run a Deployment of the same
  name → replace-in-place, risk retired); §4.3.2's binary check (two wrong paths that would report
  false MISSes on the two most important tools); §1's scope ("20 commits" — the release actually
  carries ~41, because 21 `legacy/` commits already merged via the G3-748 PR have never reached
  SQA/Stage/Prod). Checking §4.3.1 also surfaced a *new* risk: no overlay patches the worker's
  replica count, so deploying prod as configured takes tools-worker 2 → 1.
- **Evidence:** commit 0d36c639; `kubectl get deploy` across dev/sqa/stage/prod.
- **Applies when:** inheriting or resuming a plan. Its open questions are often one command away,
  and answering them tends to surface adjacent risks nobody listed.

### 13. Derive denormalized values from the source of truth, not a parallel count
- **Description:** The fix for GWC-34 was not to correct the staged-row count but to stop counting
  separately: `SET gs_count = (SELECT count(*) FROM extsrc.geneset_value WHERE gs_id = …)` after
  the insert. It cannot drift again regardless of how the INSERT changes.
- **Evidence:** commit a133bd2b; re-verified on dev as 2 vs 2.
- **Applies when:** maintaining any denormalized counter/cache column. Compute it *from* the rows
  it describes; ordering matters (write it after the rows exist).

## Key Decisions (cont.)

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Derive `gs_count` from `geneset_value` rather than fix the staged count | Self-correcting; immune to future INSERT changes | a133bd2b; verified on dev |
| Separate commit for strengthened tests, not `--amend` | `a133bd2b` was already cited in two Jira comments; amending would break those references | 3908c1cd |
| Exclude empty-but-counted genesets from the backfill | A blanket backfill would silently rewrite ~1.6% of live genesets to 0; cause unknown, needs a product decision | Recorded on G3-782, asked the reporter on GWC-34 |
| Fix GWC-34 in legacy though v3 shows the same wrong number | Every *writer* of `gs_count` is legacy (v3 has no upload path); both read the same column, so the legacy fix corrects v3 too | G3-782 under G3-769 |
| Stop at prod's RBAC denial rather than route around it | `pods/exec`, `portforward` and `secrets` are all denied on prod; the remaining routes meant pulling prod DB credentials into the session | Reported the block; used sqa instead |
| G3-784 requires *both* halves (DB-resolved **and** full gene space) | Resolving from the DB still rejects Tier-IV sets; widening the universe still goes stale | Story G3-784 under epic G3-763 |
| Retrospective G3 ticket for an already-fixed, already-merged bug | GWC-51 had no G3 counterpart, so it was absent from the umbrella and the release verification list and would have shipped unverified | G3-783 |

---

# Round 3 — GWC-34 upload path, G3-805 homology, docs ownership, PR #2 security review

> Extracted: 2026-08-16
> Source: same branch (`fix/G3-769-legacy-bug-fixes-and-improvements`), merged as PR #2
>   on 2026-08-14, plus PR #3 (docs consolidation) and PR #4 (GWC-35 note).
>   Commit range `0d36c639..77161d1b` — the work after Round 2's cutoff.
> Campaign file: none. Postmortem: none. Telemetry: none (`.planning/telemetry/` absent).

## Successful Patterns (cont.)

### 14. Fix *every* writer of a denormalized value, not the one you reproduced
- **Description:** Round 2 fixed `gs_count` in `insert_into_geneset_value_by_gsid()` and the
  bug stayed live, because that path only runs on curator edits and delayed commits — a plain
  new upload never reaches it. Three separate writers held the same fault, each with a
  *different* wrong formula: `len(gene_data.split('\n'))` (submitted lines, plus the trailing
  blank line `split` yields), a `geneset_value NATURAL JOIN gene WHERE ode_pref` count (one row
  per preferred identifier a gene carries, ~2× on dev — 48 against 25 stored for GS403415),
  and the staged-rows count already fixed. Only enumerating the writers closed it.
- **Evidence:** commit 3ddd38a5; GS407881 showed 9 in My Genesets against 4 on the geneset page
  *after* the Round 2 fix shipped.
- **Applies when:** any denormalized column. Grep for every assignment to it before closing —
  the path that reproduces is rarely the only one, and per-path formulas drift independently.

### 15. Reproduce a stored-procedure bug inside a rolled-back transaction
- **Description:** Rather than reasoning about `create_geneset2`, the real procedure was called
  on dev inside a transaction that was rolled back: 8 identifiers in → `gs_count` 9, 4 rows in
  `geneset_value`. The reconstructed input reproduced the stored `file_contents` byte for byte,
  which is what proved the probe matched the user's actual upload rather than a lookalike.
- **Evidence:** commit 3ddd38a5, dev reproduction 2026-08-06.
- **Applies when:** the logic lives in a stored procedure. Rollback makes exercising production
  code on a real database cheap; byte-comparing the reconstructed input is what makes it *evidence*.

### 16. Quantify a scoring bug's direction and magnitude, not just its existence
- **Description:** G3-805 could have been reported as "Find Similar drops genes." Instead it was
  characterised: the error runs in **both** directions — a dropped gene present in only one set
  shrinks the union and *inflates* the score; one shared by both sets is dropped from the
  intersection too and *deflates* it, since `(c-k)/(u-k) < c/u`. Measured on 40 same-species
  pairs sharing a non-homologous gene: 24 inflated, 16 deflated. Blast radius on a 2,000-geneset
  sample: 8.6% of in-threshold memberships on dev, 8.4% on sqa.
- **Evidence:** commit 5c79bb0d; verified against the deployed tool on 46 pairs covering both cases.
- **Applies when:** a numeric disagreement between two features. "Which way, how far, how often"
  turns a bug report into a decision about whether to backfill, and catches the case where you
  assumed a one-directional error.

### 17. Pick a surrogate key that cannot collide with the real one
- **Description:** Keying membership by `hom_id` where a homolog exists and by the gene itself
  where it does not needs a namespace: `ode_gene_id` can be **negative**, so an integer surrogate
  like `-ode_gene_id` could collide with a genuine `hom_id`. Keys are text, `'h'`/`'g'` prefixed.
- **Evidence:** commit 5c79bb0d.
- **Applies when:** unioning two identifier spaces into one key. Check the actual domain of both
  (signs, ranges, reuse) before assuming an arithmetic trick separates them.

### 18. Split a dual-purpose query instead of leaving a near-duplicate
- **Description:** The homology fix was correct for *scoring* and wrong for *discovery* —
  `dynamic_jaccard` feeds hom_ids to `get_genesets_by_hom_id`, which looks up
  `extsrc.hom2geneset` and can only match real hom_ids. `get_geneset_hom_ids` therefore keeps its
  INNER JOIN and integer ids, while `get_genesets_hom_ids` (one caller) *became* the scoring
  function rather than being left beside it as a near-duplicate that would drift.
- **Evidence:** commit 5c79bb0d; `geneweaverdb.py:4405` (discovery) vs `:4460`/`:4498` (scoring).
- **Applies when:** one query serves two callers with different correctness requirements. Split by
  purpose and delete the redundant one — two similar queries with different semantics is a latent bug.

### 19. Verify the *visibility* path of a data migration, not just the data
- **Description:** Migration 118 corrected `gs_count` in the database and search kept serving the
  old number: `gs_count` is a materialised Sphinx index attribute (`sql_attr_uint`), not a live
  read. Worse, a **delta** reindex can never pick these up — `geneset_delta_src` selects on
  `gs_updated >= sphinxcounters.last_update`, and the backfill deliberately does not touch
  `gs_updated` (it is the user-visible last-modified time; bumping it would assert the contents
  changed). Only `indexer --all` republishes them. Checked against the running dev sidecar:
  GS407872 read 1538 in the DB while the index served 1901.
- **Evidence:** commit 93ae3aa1.
- **Applies when:** any backfill of a column that something else caches, indexes, or materialises.
  Ask what republishes it and whether the incremental path can even see your change.

### 20. Fix the reported instance, then sweep for the defect class
- **Description:** Copilot flagged one stored-XSS sink (`uploadgeneset.html:780`). The same defect
  was in three more places — missing-gene identifiers and score-type warnings in
  `uploadgeneset.html`, batch parse errors and warnings in `batchupload.html` — all rendering
  user-file content through `.html()`. Fixing only the reported line would have left the hole open.
  The rest of both upload paths were then checked: the only other `.join()` writes to an input's
  `.value`, which is not an injection path.
- **Evidence:** commit f11ae9fb; `static/js/geneweaver/escapeHtml.js` (`gwEscapeHtml`/`gwEscapeHtmlJoin`).
- **Applies when:** any review finding with a shape (a sink, a call form, a missing guard). Grep
  the shape; report both what you fixed and what you checked and cleared.

### 21. Prove content parity by hash before replacing a publishing pipeline
- **Description:** Before moving the docs site into the monorepo, parity was established rather
  than assumed: all 271 files under `geneweaver-docs/docs` exist here, every asset hashes
  identically, and the only differences are three tutorial notebooks whose cell *sources* differ
  by formatting alone (quote style, import order, wrapping) from having been formatted after
  import. The monorepo is a strict superset — which is what made archiving the old repo safe.
- **Evidence:** commit d9fa4e67.
- **Applies when:** retiring a source of truth. "We copied it over once" is not parity; hash it.

### 22. Turn on `--strict` and treat what it surfaces as real breakage
- **Description:** The new docs build runs `--strict`, which the old pipeline did not. It surfaced
  eight pre-existing broken links — seven images referenced as `images/*.png` that live in
  `docs/assets/images/`, and a link to a page moved to `analysis-tools/index.md`. All were live
  user-visible breakage on the published site, invisible because the old build tolerated them.
- **Evidence:** commit d9fa4e67.
- **Applies when:** adopting a stricter build. The first run is a free audit of the old one — budget
  for fixing what it finds rather than relaxing the flag.

### 23. Reason about CI permission caps before the first run, not after the 403
- **Description:** A called reusable workflow cannot hold permissions its caller does not grant,
  and requesting *more* than the caller grants is an error. With the repo default
  `default_workflow_permissions: read`, `_docs-action.yml`'s `contents: write` would have been
  capped and `gh-deploy`'s push rejected. The grant went on the callers
  (`docs-release.yml: write`, `docs-pull_requests.yml: read`) rather than into the shared action,
  because pinning it inside would have broken the build-only PR job.
- **Evidence:** commit e1ac74aa. Explicitly left unverified: whether an org-level Actions policy
  also caps escalation — reading that needs org admin, and it was named as the next thing to check
  if the publish still 403s.
- **Applies when:** shared/reusable CI workflows. Permissions intersect downward; put the grant at
  the caller and record what you could not verify.

### 24. Name a constraint a *release* gate when it is not a merge gate
- **Description:** Repointing the app's Help links to the monorepo docs is safe on dev and breaks
  prod: the monorepo is internal, so its Pages site is org-only, and external geneweaver.org users
  would hit an org login where documentation used to be. Rather than blocking the merge or leaving
  a comment in a workflow file, it was recorded as a numbered release precondition (B9) beside the
  other G3-781 prod prerequisites, so it is checked at the same moment as everything else.
- **Evidence:** commits 5a712ad8, d35f8aec, 3f34285b, d2a853a6.
- **Applies when:** a change is correct for the current environment and wrong for a later one.
  A gate recorded where the promotion checklist lives gets checked; a code comment does not.

### 25. Make a test independent of collection order rather than renaming around it
- **Description:** `tests/db/test_get_genesets_hom_ids` shims `tools` as a `MagicMock` so
  `geneweaverdb` imports without psycopg2 — which made `from tools.MSET import ...` resolve against
  that mock when it ran first: the new test passed alone and failed in the suite. Fixed by dropping
  foreign `tools` entries before importing and restoring them afterwards, then verifying in **both**
  orders.
- **Evidence:** commit 5651bbcd (`tests/tools/test_mset_background_check.py`); gate green at 89 tests.
- **Applies when:** a suite where any module mutates `sys.modules` at import time. Fix the coupling
  and prove it with both orderings — ordering-dependent passes are noise that later reads as flake.

### 26. Tell the user what they cannot fix themselves
- **Description:** The MSET background message named the offending genes and stopped, so users
  reasonably assumed it was theirs to correct. It is not — the background is built from curated
  gene sets and only an administrator can change a curation tier. The message now says so and
  directs them to the team.
- **Evidence:** commit 5651bbcd (QA feedback on GWC-51); tests cover the contact direction, gene
  names and counts, truncation past 15 genes, silence on a clean list and on a missing background
  file, and that raw C++ stderr never reaches the user.
- **Applies when:** writing a user-facing error for a condition the user has no permission to fix.
  Accuracy about the cause is not the same as telling them what to do next.

### 27. Accept the review point that contradicts your own document
- **Description:** PR #3's review disputed a precondition the author had written — that archiving
  `geneweaver-docs` prevents a publish race. It does not: each repo's `gh-deploy` pushes to its own
  `gh-pages` and serves its own project path, so the two cannot overwrite each other. Recorded
  plainly as "this was my error — the old wording would have blocked the rollout for no reason,"
  and the constraint reworded to what it actually is (retiring a second, diverging copy).
- **Evidence:** commit d2a853a6, point 1.
- **Applies when:** review challenges a constraint you authored. A precondition that is not one
  costs real delay; verify the mechanism rather than defending the sentence.

## Key Decisions (cont.)

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Correct `gs_count` *after* `create_geneset2` rather than fix the value passed in | The proc stores the count verbatim and only afterwards calls `reparse_geneset_file()`; nothing reconciled them. Deriving post-hoc is immune to how the proc resolves identifiers | 3ddd38a5, `uploadfiles.py:287-313`; probe stores 4, agreeing with `get_genecount_in_geneset` |
| Migration 118 excludes genesets that claim genes but hold none | 2,920 on dev, one claiming 13,190; re-running the resolver restores nothing (source files uploaded comma-separated where TSV was expected, or species whose gene data is not loaded). Zeroing them changes search results | Left as a product decision; read-only drift report added at `migration/checks/gwc34-gs-count-drift.sql` |
| State plainly that the fix makes counts *smaller* | The correction reduces counts where identifiers failed to resolve; without saying so it reads as a fix for GWC-36 (dropped genes), which it is not | CHANGELOG rewritten in 4e074beb; verification row expects a count *below* the number of identifiers submitted |
| Leave the batch path unchanged | `BatchReader.__map_gene_identifiers` already returns the resolved, deduped count — consistent with all 192,261 bulk-loaded genesets on dev being exact while every interactively created one drifted | 3ddd38a5 |
| Keep `gs_updated` untouched in the backfill | It is the user-visible last-modified time; bumping it would assert the contents changed when only a cached total was repaired, disturbing curation views and recently-updated sorting | 93ae3aa1; accepted cost is that only `indexer --all` republishes |
| Promote two guardrails from `.planning/knowledge` into `CLAUDE.md` | Citadel gitignores `.claude/harness.json` as local state, so harness rules only protect whoever runs Citadel; `CLAUDE.md` is the version the team actually gets | 33e327e2 (SQL parameterisation, denormalized counts) |
| Commit `.planning/knowledge/` to the repo | `CLAUDE.md:5` pointed at it for the evidence behind the guardrails, but it had never been tracked — so for anyone cloning, the reference went nowhere | 5e1aea86; contents checked first (incident text and config key names only, no secret values) |
| Deliberately **not** sweep `[project.urls].Homepage` in pyproject files | Those publish to PyPI; pointing public package metadata at an org-only Pages site is worse than pointing at the old public site, which stays served read-only after archiving | Recorded under B9 to move when Pages becomes public (d2a853a6) |
| Rewrite the carried-over issue template instead of copying it byte-for-byte | The original was `feature_request.md` with only the front-matter name changed — its `about` and body still asked about feature requests under a "Documentation request" heading | 02a615ea; offered to revert to byte-identical if preferred |
| Grant `contents: write` at the callers, not in the shared action | Permissions intersect downward *and* a callee requesting more than its caller grants is an error — pinning it inside would have failed the build-only PR job | e1ac74aa |
| Ship Help links to an internal Pages site now, gate on prod | Acceptable while the docs ride on dev; must be public (or moved to a custom domain) before prod or external users hit an org login | 5a712ad8 + B9 in `LEGACY_CICD_MIGRATION.md` |
| Document *both* settings needed to reproduce a Similar Genesets score | Homology = Included **and** Pairwise Deletion = Disabled. Documenting only the homology half would set up the same confusion again — Find Similar has no pairwise-deletion equivalent | 26f173f2 (GWC-35, requested by Tessa Nichols-Meade); verified by building the site and checking the rendered page |
