# GeneWeaver Legacy — Changelog

Changes to the legacy GeneWeaver application (`legacy/`), released from the monorepo via
`.github/workflows/legacy-release.yml` and tagged **`v<version>`** (e.g. `v1.6.0a`).

**Pushing the tag is the release decision** — merging a version bump to `main` deliberately does
*not* release (`cb61c111`; a merged branch carrying a bump once fired an unintended prod-bound run).
The tag must match `legacy/pyproject.toml` or the run fails. A version containing a letter is a
pre-release and deploys to **SQA only**; a plain version promotes through Stage and Prod.

---

## 1.6.0b — unreleased

The post-sign-off fix set. Everything here was found **after** 1.6.0a was signed off on SQA — six
findings raised while running the §6 verification list, two more just after, plus a fourth
threshold divergence found in code review. A **pre-release, SQA only.**

> **Scope note.** No database migration is required for this release, and no gene set's membership
> changes anywhere. Migration 119 is carried over from 1.6.0a's follow-up work and is already
> applied to dev and sqa; Stage and Prod still need it (G3-821, G3-822). A migration 120 was drafted
> and then **deleted** — see *Decided* below.

### Fixed — curation & upload

* **Tool-generated gene sets bypassed threshold processing entirely** (G3-809) — `56152dc2`,
  `e4d976dc`. `/createtempgeneset` and `/creategeneset.html` each carried a byte-identical inline
  block that flagged `gsv_in_threshold` from a hardcoded `avg in [-1, 1]` rule — a rule matching no
  score type, evaluated *before* `gs_threshold_type` was known — and never called
  `process_thresholds` or `recompute_geneset_value_thresholds`. So tool-created sets carried
  membership that agreed with nothing, and migration 117 and the Python threshold fixes never
  reached them. Both routes now go through the one shared implementation. The extracted helper's
  `geneset_value` INSERT is also fully parameterised: it had been hand-building PostgreSQL array
  literals, which breaks on any reference identifier containing a quote or backslash.
* **A batch P-Value/Q-Value threshold could never validate** (G3-811) — `b3a23de2`, `1128fece`.
  `validate_pq_value` matches a bare number, but the whole line (`P-Value < 0.05`) was passed to it,
  so every thresholded line fell through and the user's cutoff was silently replaced with `0.05`.
  Now parsed correctly — and only an *exact* bare keyword defaults silently: `P-Value > 0.01` and
  `P-Value 0.01` used to be treated as a deliberate default rather than the malformed headers they
  are, so they replaced the cutoff with no warning at all.
* **Changing a score type ran no value-domain check** (G3-812) — `0adc51c5`. The GWC-42 half-gap:
  the upload paths validated values against the score type, but the after-the-fact change did not,
  so a curator could reinterpret existing values under a new type with no signal they were
  nonsensical. Advisory, matching the upload behaviour — it warns, it does not block.
* **Creating a gene set from a tool result silently dropped genes with no Homologene row**
  (G3-815) — `50783c21`. `transpose_genes_by_species` resolved the gene list *through*
  `extsrc.homology`, so a gene absent from Homologene could not survive the join — even on a
  same-species transpose where nothing needs transposing. Measured on SQA during sign-off: 6 of 115
  genes lost, with no warning anywhere in the UI. Unchanged since April 2018.

### Fixed — search

* **The Sphinx index was only ever built when a pod was replaced** (G3-814) — `f939aba6`,
  `bc4a5103`, `9a51273e`. `start_sphinx.sh` ran `indexer --all` once at container start and then
  `searchd` took over the process, so index freshness was incidental to pod lifecycle — a new gene
  set could be missing from search for weeks. The main+delta machinery was fully configured and
  already queried by `search.py`; only a scheduler was missing. Now a delta rebuild every
  `SPHINX_DELTA_INTERVAL` (default 15 min) plus a full rebuild at 00:00 America/New_York, with
  `tzdata` installed and `TZ` set so the schedule holds across the EST/EDT transition. Three
  related fixes: the cold build is now **fatal** (it fell through to `searchd`, which then served an
  absent index while looking healthy to Kubernetes); each replica keys its watermark rows
  separately, because the prod overlay runs `replicas: 4` against two shared
  `production.sphinxcounters` rows and interleaved rebuilds could leave the delta reading a NULL
  watermark and silently indexing nothing; and **`update_geneset` now bumps `gs_updated`**, which
  was previously written only when the edit page was *opened*, so a page held open across the
  nightly rebuild produced a save no delta could ever see. The inert packaged
  `/etc/cron.d/sphinxsearch` is removed rather than left to mislead.
* **`/searchFilter.json` 500 on a request with no `searchbar` field** (G3-818) — `f5d0d0d0`. The
  fourth crash in this route after G3-778's three: `render_search_json` passed
  `[form.get('searchbar')]` straight through, so an absent field reached
  `'@(' + search_fields + ') ' + t` with `t = None`. Guarded in the shared sink rather than the
  route — the page route already checked, the JSON route did not, and a third caller would have
  inherited it. An empty search now degrades to the no-results state both routes already render.
  `int(form.get('pagination_page'))` on the same route failed the same way and now defaults to 1.

### Security

* **The admin data-table endpoints were SQL-injectable** (G3-816) — `628cb904`. They built SQL by
  `%`-interpolating request parameters and ran it with no bound parameters; psycopg2's `execute`
  hands the string to libpq `PQexec`, so statements stacked after a `;` also ran — write and DDL,
  not read-only. Values are now bound, and table and column names are resolved against an allowlist
  of the eleven tables the admin viewer actually offers (validating against `information_schema`
  alone would still permit `table=production.usr&columns[0][name]=apikey`, which was one of the
  vectors).

  Two of the four routes turned out **not** to be admin-gated at all:
  `/getServersideGenesetsdb` and `/getServersideResultsdb` have no decorator and no `is_admin`
  check, and `before_request` only *looks up* the user without gating — so `search[value]` there was
  an **unauthenticated** injection. Both also took the `user_id` to filter on straight from the
  request, letting anyone list any user's gene sets or tool results by guessing an id; they now
  require a session user and use that id. Also parameterised `get_primary_keys` (request-fed from
  both admin write routes), `admin_get_data`, `get_all_columns`, `get_required_columns` and
  `get_nullable_columns`, and extended the table allowlist to `admin_set_edit` and `admin_add`,
  which were injection-safe but would write to any table the request named.

### Decided — the P/Q threshold boundary stays exclusive (G3-819)

* `271f6e90`, and migration 120 **deleted**. A fourth divergence in the G3-809 family, found in
  review: `process_thresholds` treated the P/Q cutoff as exclusive (`<`) while
  `recompute_geneset_value_thresholds` and `batch.__check_thresholds` treated it as inclusive
  (`<=`), so a value exactly on its cutoff was a member or not depending on which path last wrote
  it.

  The code's intent read inclusive, but the deployed behaviour decided it: of the type-1/2 rows
  sitting exactly on their cutoff, **none** were in-threshold — 0 of 28,205 across 601 gene sets on
  sqa, 0 of 14,431 across 590 on dev. No mixture, because the procedure is the effective writer for
  all of them. Exclusive is what every environment including Prod has always stored. Going inclusive
  would have retroactively added members to ~600 published gene sets per environment across every
  curation tier, some created in 2007 (GS407228 +13,440 genes; GS793 +45%) — a change to the
  scientific record, not a fix. **So the Python paths came down to `<` and the databases were left
  untouched.** `application.calc_genes_count_in_threshold` — the `/setthreshold` preview count shown
  to curators — was also `<=` while membership was `<`, so the page could promise more genes than
  the set would hold; now consistent with its own docstring. Two-sided score types
  (Correlation/Effect) remain inclusive everywhere; that was never in question.

### Added

* **A read-only drift check for migration 117** (G3-810) — `948c5f7e`.
  `legacy/migration/checks/gwc44-binary-threshold-drift.sql` reports rows to change, whether the
  procedure is patched, and whether the backfill audit is present. Safe to run in any environment at
  any time.

### Infrastructure & operations

* **Migration 119** (G3-809) — `2cd5ffc6`, `f1faafa8`.
  `legacy/migration/119-fix-correlation-effect-abs-threshold.sql`. `process_thresholds` computed
  Correlation/Effect (types 4/5) membership as `ABS(gsv_value) BETWEEN lo AND hi` while both Python
  paths used the signed value, so membership depended on which path last ran. `ABS` only diverges on
  *asymmetric* ranges, and there it is wrong twice over: for `6.0 < Effect < 22.50` it silently also
  admits the −22.50..−6.0 band, and for an auto-derived type-5 set it excludes the most-negative
  genes that *defined* the minimum. **Already applied to dev and sqa** (audits at 82,192 and 111,493
  rows, backfill complete, zero rows still disagreeing); Stage and Prod outstanding — G3-821,
  G3-822.
* **JaccardSimilarity's distribution caches** (G3-817) — no code change; an operational step per
  environment. `genes.dat` / `homology.dat` are regenerable sampling caches on the results PVC, not
  image content (`e3e4ad03`). They were absent on SQA, so `distribution_generator` returned `-1`
  without inserting and JaccardSimilarity reported `p = 0` for any set-size pair not already cached.
  **Generated and verified end-to-end on sqa 2026-09-04**; dev has had them since 30 June. Stage and
  Prod each need the same one-off step — procedure in the release plan §4.3.3, and note the GCSFuse
  guardrail: generate to local disk and bulk-copy, never write the ~200 MB file straight to the
  mount.

### Testing & developer tooling

* Regression cover for the review findings and the third G3-778 bug — `f33c3c68`, `bb6403c2`, and
  the tests landing with each fix above. The legacy suite goes **87 → 150** and the CI module list
  9 → 15 (measured against `main`, not the 48 an older note recorded — tests landed between that
  note and the 1.6.0a cut). Every module is wired into the explicit list in `_legacy-tests.yml`; a
  new module is invisible to CI until it is added there. The G3-816 and G3-809 tests are
  mutation-checked: reintroducing the interpolation makes them fail.

### Documentation

* Release plan §5.5 (migration 119), §5.6 (the boundary decision), §4.3.3 (the distribution-cache
  step, whose documented command was wrong — `fileGenerator -g -h` silently does `-g` only, since
  `main()` reads `argv[1]` and ignores the rest), and §6.1's SQA verification record — `9c0b9171`,
  `d57b1ffd`, `5c38f46d`, `8110a0fa`, `590097e9`.
* CLAUDE.md guardrails — `4ac04579`: never amend a migration that has already been applied (check
  the live database, not ticket scope), and treat a membership/threshold rule change as a semantics
  decision needing measurement and approval rather than a cleanup.

### Known issues

* **G3-813 is closeable, and is *not* a Prod gate.** It was raised on the assumption that the
  monorepo's Pages site is org-only. It is not: fetched unauthenticated from outside the org, `/`
  and `/analysis-tools/mset/` both return HTTP 200 with the real page. Recheck once before Prod.
* The 1.6.0a known issues below still stand — the empty-gene-set population (G3-782), MSET's
  Tier-IV/V rejection (GWC-51 / G3-783) and the hardcoded NCBO key (G3-770) are unchanged by this
  release.
* **v3 divergence, deliberately left alone.** `packages/core`'s `one_sided_threshold` is `<=`, with
  boundary tests asserting it, and now disagrees with legacy's `<`. Out of scope for this legacy
  release; whoever runs the v3 switchover must reconcile it, or v3 will silently change membership
  for every set with an on-cutoff value.

### Version

* `legacy/pyproject.toml` 1.6.0a → **1.6.0b**. A pre-release (the letter is what marks it), so the
  release workflow deploys to **SQA only**. Release with `git tag v1.6.0b && git push origin
  v1.6.0b` on the commit carrying this bump — the bump alone does not release. The app footer will
  read `1.6.0b0`; Poetry normalises the version, exactly as `1.6.0a` rendered `1.6.0a0`.

---

## 1.6.0a — released to SQA 2026-08-24

First legacy release cut from the **monorepo**. Previous releases (through 1.5.27) came from the
standalone `geneweaver-legacy` repo; see [`docs/ci-cd/G3-781_LEGACY_RELEASE_PLAN.md`](../docs/ci-cd/G3-781_LEGACY_RELEASE_PLAN.md)
for the promotion and cutover procedure.

> **Scope note.** SQA / Stage / Prod last received a build from the standalone repo at **1.5.27**, so
> this release promotes *two* bodies of work at once:
>
> * **`branch`** — the G3-769 bug-fix set, on `fix/G3-769-legacy-bug-fixes-and-improvements` (PR #2, merged `77161d1b`).
> * **`main`** — monorepo-migration-era work already merged to `main` via the G3-748 migration PR, which has **never** reached SQA/Stage/Prod.
>
> Each entry below is tagged accordingly. The `main` set is easy to overlook because it does not
> appear in `origin/main..<branch>` — but it ships all the same, and a large part of it is
> tools-worker behaviour.

### ⚠️ Required before deploying

* **Database migration 117** — `legacy/migration/117-fix-binary-threshold-not-thresholded.sql` must
  be applied to each environment's database **before** that environment's deploy, or the UI upload
  path keeps producing unusable binary gene sets. Idempotent; the backfill is not reversible without
  capturing pre-state first (see the release plan §5.1).
* **Database migration 118** — `legacy/migration/118-backfill-inflated-gs-count.sql` corrects the
  `gs_count` values already stored wrong. Not required for the code to be correct — the code fix
  stops *new* drift — but without it the reporter still sees the original symptom on existing
  genesets. Idempotent, and reversible via the audit table it captures. **Applied to dev
  2026-08-06** (33 genesets, 1,792 phantom genes; GS407881 9 → 4); pending SQA/Stage/Prod. It scans
  `extsrc.geneset_value` (~20s over 35M rows on dev, larger on prod), so time it on Stage first —
  Stage and Prod share a Cloud SQL instance. Procedure and per-environment status: release plan §5.4.
  To check any environment (read-only, safe any time) or to detect a later recurrence, run
  `legacy/migration/checks/gwc34-gs-count-drift.sql`.
* No Sphinx reindex step is needed — the search sidecar runs `indexer --all` at pod start, so a
  rollout rebuilds the index automatically. Apply both migrations *before* the deploy so the
  rebuilt index picks up corrected values.

### Fixed — curation & upload

* **Annotation generator broken since ~June 2025** (GWC-8 / G3-767) — `456d0147`, `c2be6326`,
  `79272f93` · `branch`
  Ontology annotations could not be generated at all. Also filters NCBO ontologies to supported
  acronyms, and hides the non-functional Monarch / "Both" annotator options in account settings.
* **Genes silently dropped on upload** (GWC-36 / G3-768) — `4680637b`, `519d45a1` · `branch`
  Gene identifiers that were aliases or synonyms rather than the official symbol were discarded
  without warning, so uploaded sets were quietly smaller than the submitted list.
* **No score-type validation; score type not editable** (GWC-42 / G3-772) — `cedfee9e`, `53c29cfd`,
  `e07015e0` · `branch`
  Out-of-range and invalid score values are now reported instead of silently accepted, on both batch
  and single-geneset upload, and the score type can be changed on an existing set. Includes a fix to
  batch Correlation/Effect threshold parsing, which read the wrong regex group.
* **Binary gene sets were thresholded on upload** (GWC-44 / G3-776) — `2e737f01` · `branch` ·
  **requires migration 117**
  Binary (membership) sets had their genes marked out-of-threshold, making them unusable in every
  analysis tool. The stored procedure now always treats `gs_threshold_type = 3` as in-threshold, and
  migration 117 backfills existing sets.
* **Search-result gene counts disagreed with the geneset page** (GWC-34 / G3-782) — `a133bd2b`,
  `3ddd38a5` · `branch` · **backfill migration 118**
  Search and the My Genesets Count column render the stored `gs_count`; the geneset page counts
  live. Three write paths stored a count that was never derived from the genes actually saved, so
  the two disagreed — always in the direction of over-counting:
  * **Plain UI upload** — `gs_count` was `len(gene_data.split('\n'))`, i.e. submitted *lines* plus
    the trailing blank one, handed to `create_geneset2`, which stores it verbatim and only then
    calls `reparse_geneset_file()` to resolve identifiers. Identifiers matching no gene are dropped
    and identifiers for the same gene collapse, and nothing reconciled the count afterwards.
    Verified on dev: GS407881 submitted 8 identifiers, stored `gs_count` 9, saved 4 genes.
  * **Geneset edit / delayed upload** (`a133bd2b`) — counted staged rows in `temp_geneset_value`
    while the INSERT groups by `ode_gene_id`, so alias/duplicate identifiers inflated it.
  * **Tool-generated genesets** (`genesetblueprint`) — counted
    `geneset_value NATURAL JOIN gene WHERE ode_pref`, one row per *preferred identifier* a gene
    carries rather than one per gene (avg ~2 on dev), roughly doubling the count; it also raised
    `TypeError` on an empty geneset because `GROUP BY gs_id` returned no row.

  All three now derive the count from `extsrc.geneset_value` after the rows exist. Note this makes
  the count *honest*, not larger — where identifiers failed to resolve the displayed number will
  drop (GS407881: 9 → 4). Genes are still being dropped on upload; that is GWC-36, not this ticket.
* **Admin-page tier change and geneset edit view** (GWC-9 / G3-775) — `35e47977` · `branch`
  Changing a geneset's tier from the admin page had no effect, and some genesets returned a 500
  when opening the edit view.

### Fixed — search

* **Search robustness: three bugs** (G3-778) — `4fee2bb4` · `branch`
  `/searchFilter.json` returned HTTP 500 on zero-result queries; a request without a sort parameter
  raised `UnboundLocalError`; and a filter facet with nothing selected produced an empty `IN()` that
  zeroed the entire result set instead of meaning "no restriction".
* **Find Similar Genesets thresholded only one side** (GWC-35 / G3-780) — `ac0a986c` · `branch`
  The viewed geneset was filtered to in-threshold genes but candidate genesets were not, inflating
  similarity scores. On a live dev sample, 67 of 300 candidates were affected; none were inflated
  after the fix.

### Fixed — analysis tools

* **BooleanAlgebra "Symmetric Difference" returned a 500** (GWC-50 / G3-765) — `1ad89158` · `main`;
  `3d1f67b9` · `branch`
  Plus: a `venn.js` failure no longer blanks the whole diagram for 3-or-more-set comparisons.
* **MSET "list not a subset of its background"** (GWC-45 / G3-766) — `b82688d1` · `main`
  Backgrounds had gone stale after the December-2025 gene reload. Regenerating them fixes it; note
  this was a **dev-only data refresh** — re-check per environment rather than assuming it is needed.
* **MSET: cryptic error for Tier-IV gene sets** (GWC-51 / G3-783) — `0ba54c0a` · `main`
  A Tier-IV geneset can contain real genes that are outside the curated background, which MSETcpp
  correctly rejects — but the user saw a generic 500 containing raw C++ stderr. The failure is now
  reported clearly, naming how many genes are outside the background and which ones. **The
  underlying limitation is unchanged and deliberate** (deferred to the V3 tools port), so the
  expected outcome when verifying is a readable message, not a successful run.
* **MSET internal server errors (Python 2 → 3)** — `fa492116` · `main`
* **MSET worker crash and wrong list-2 background** — `1ecba34a` · `main`
* **DBSCAN crashed when a run produced no clusters** or the binary failed — `bd30502b` · `main`
* **Graphviz `dot` not found** — `7416c3dc` · `main` — resolved from `PATH` rather than a fixed path.
* **`distribution_generator` produced "invalid byte sequence for encoding UTF8"** — `f69400fb` ·
  `main` — a dangling `.c_str()` pointer into a freed temporary.

### Security

* **Auth0 `client_secret` was logged in plaintext** at CRITICAL on every startup (G3-761) —
  `69d86897` · `main`
  The secret was reaching pod stdout and Cloud Logging on each boot. Treat any secret that was live
  before this release as exposed and rotate it if that has not already been done.

### Added

* **Batch upload accepts pasted text**, not only a file (`29b9338b` · `branch`) — a paste/editor box
  alongside the file picker.

### Infrastructure & operations

* **tools-worker is now built and deployed by the monorepo** — `c3b1b489`, `348c2cfd` · `main`
  A single Linux image carrying all tools plus the compiled TOOLBOX binaries, deployed as the
  `geneweaver-legacy-tools` Deployment sharing the `geneweaver-pvc` with the web app. Every
  environment already runs a Deployment of that name, so this **replaces** the existing worker in
  place rather than adding a second consumer of the Celery queue. ⚠️ Prod currently runs **2**
  replicas and nothing in the manifests patches the worker's replica count, so deploying as
  configured would scale it to 1 — see the release plan §4.3.1.
* **TOOLBOX database connections are env-driven**, and libpqxx is pinned to 6.4.8 — `14359acb` ·
  `main` (the legacy C++ uses the ≤6 API that libpqxx 7 removed).
* **`genes.dat` / `homology.dat` paths are env-driven** (PVC-backed) — `e3e4ad03` · `main`.
  These files are not in the image; confirm the target directory is a mounted volume that already
  holds them before exercising any tool that reads them.
* **Recovered tools-worker source preserved in-repo** — `bed8967b` · `main`. The production worker
  image had been built from an uncommitted tree; the source is now version-controlled.
* **Legacy CI/CD pipeline and per-language lint setup** — `478e8ed0` · `main`.

### Testing & developer tooling

*No runtime impact.*

* **Legacy regression suite + CI gate** (G3-779) — `f7196d77`, `e3d6fdde`, `3908c1cd`, _this branch_
  · `branch`
  74 pure unit tests covering the fixes above, gating both the PR build and the release.
  Note `_legacy-tests.yml` enumerates test modules explicitly — a new test file must be added there
  or CI silently skips it. Two additions closing gaps found by auditing coverage against the full
  release contents:
  * **GWC-36 / G3-768 was untested.** The fix lives in `get_gene_ids_by_spid_type`, and no test
    referenced that function — the suite's only GWC-36 mention covers `process_gene_list`, a
    different function. `tests/db/test_gene_id_mapping.py` now pins both halves of the fix: that
    `ode_pref` no longer filters rows (or alias-only symbols are silently dropped again) and that it
    still leads the `ORDER BY` so the preferred gene wins a symbol collision. Verified to fail
    against the pre-fix code, and against a simulated re-introduction of the `ode_pref` filter.
  * **`tests/db/test_get_genesets_w_threshold_counts.py` could never have run.** It imported a
    function name that does not exist and asserted a list-of-dicts shape where the real function
    returns `{gs_id: count}`, so all four tests failed on import; being outside the gate, nothing
    reported it. Rewritten against the real signature and added to the gate. It also pins that
    genesets with no in-threshold genes are *absent* from the mapping rather than mapping to `0`,
    which G3-785 has to handle.

  Still uncovered after this pass, in rough priority: the `render_search_json` no-results guard
  (1 of the 3 bugs in G3-778), the GWC-8 annotator, GWC-9, and the whole already-in-`main` set —
  MSET (Python 2→3, Tier-IV messaging, worker crash), DBSCAN, graphviz, the C++ `c_str()` fix and
  the Auth0 secret-logging fix. §1 of the release plan flags that set as where release risk
  concentrates.
* **dev-vs-sqa tool A/B harness** — `5a7e44b3`, `1545471c`, `eec91092`, `b567a7d0` · `main`
  Compares tool output across environments; tolerant of remapped `ode_gene_id`s, and only reports a
  match when both runs actually succeeded.
* **`run-local.sh`** brings up the full local stack — `3ea02966` · `main`.
* Vendored legacy JS excluded from lint — `77ba9eb9` · `main`.

### Documentation

* NCBO API-key removal and rotation tracked as a follow-up (G3-770) — `53731db1` · `branch`.

### Known issues

* **Genesets with a count but no genes** (G3-782) — 2,920 live genesets on dev (~1.5%) carry a
  non-zero `gs_count` with no gene rows at all, and are searchable; the worst claims 13,190 genes.
  Cause not yet established; deliberately **excluded from migration 118** pending a decision, since
  zeroing them changes what search returns. Raised with the reporter on GWC-34, unanswered. Until
  it is decided, a user can still hit a geneset whose search count does not match its page — it
  will be one of these empty ones rather than a miscount.
* **MSET rejects Tier-IV/V gene sets** whose genes fall outside the curated background (GWC-51 /
  G3-783). By design for now; the V3 tools port should define the background as the full gene space.
* **NCBO API key is still hardcoded** (G3-770) — deliberately retained in this release to avoid
  re-breaking the annotator; move it into the external secret and rotate it.

### Version

* `legacy/pyproject.toml` 1.5.27 → 1.6.0 (`e888036d` · `branch`), then **cut as the pre-release
  `1.6.0a`** (`f3447c46`) and tagged `v1.6.0a` — deployed to SQA on 2026-08-24 (run `32744456037`),
  with Stage and Prod skipped as designed. Note the release trigger moved to the tag in `cb61c111`;
  pushing a version bump to `main` does **not** release.

---

<sub>Covers all 41 commits touching `legacy/` in this release: 20 on
`fix/G3-769-legacy-bug-fixes-and-improvements` and 21 already on `main` from the G3-748 migration PR.
Two further commits on the branch are repo-level chores that do not affect the legacy application and
are omitted: `0f77eeb7` (gitignore for env-variant secrets, DB dumps, compiled binaries) and
`a344cc0d` (CLAUDE.md engineering guardrails, local-DB seed scripts).</sub>
