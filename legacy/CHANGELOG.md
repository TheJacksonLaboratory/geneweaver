# GeneWeaver Legacy — Changelog

Changes to the legacy GeneWeaver application (`legacy/`), released from the monorepo via
`.github/workflows/legacy-release.yml` and tagged `legacy-v<version>`.

---

## 1.6.0 — unreleased

First legacy release cut from the **monorepo**. Previous releases (through 1.5.27) came from the
standalone `geneweaver-legacy` repo; see [`docs/ci-cd/G3-781_LEGACY_RELEASE_PLAN.md`](../docs/ci-cd/G3-781_LEGACY_RELEASE_PLAN.md)
for the promotion and cutover procedure.

> **Scope note.** SQA / Stage / Prod last received a build from the standalone repo at **1.5.27**, so
> this release promotes *two* bodies of work at once:
>
> * **`branch`** — the G3-769 bug-fix set, on `fix/G3-769-legacy-bug-fixes-and-improvements` (PR #2, not yet merged).
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

* `legacy/pyproject.toml` 1.5.27 → 1.6.0 (`e888036d` · `branch`). Pushing this version bump to `main`
  is what triggers the release workflow.

---

<sub>Covers all 41 commits touching `legacy/` in this release: 20 on
`fix/G3-769-legacy-bug-fixes-and-improvements` and 21 already on `main` from the G3-748 migration PR.
Two further commits on the branch are repo-level chores that do not affect the legacy application and
are omitted: `0f77eeb7` (gitignore for env-variant secrets, DB dumps, compiled binaries) and
`a344cc0d` (CLAUDE.md engineering guardrails, local-DB seed scripts).</sub>
