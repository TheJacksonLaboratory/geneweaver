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
