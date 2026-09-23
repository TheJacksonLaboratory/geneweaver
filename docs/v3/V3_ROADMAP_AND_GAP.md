# GeneWeaver v3 — roadmap & backend gap analysis

> Ordering for the v3 work tracked under epics **G3-763** (Switch from GeneWeaver legacy to
> GeneWeaver V3) and **G3-786** (New GeneWeaver UI — feature parity), plus an analysis of legacy
> backend capability that is **neither built nor ticketed**. Companion to
> `docs/ui/NEW_UI_GAP_AND_PLAN.md` (which this document re-sequences) and
> `docs/tools/TOOLS_BENCHMARKS.md` / `TOOLS_MIGRATION.md`.
> **Last updated:** 2026-09-23

---

## 1. Why this document

The v3 backend (`src/geneweaver/api`) exposes **23 routes, only 4 of which change state**, and mounts
only `genesets`, `genes`, `publications`, `species`, `search` and `monitors`. The nine ported
analysis tools in `packages/tools` — the part of v3 with measured correctness and performance
wins over legacy — are **not reachable through v3**: `geneweaver-tools` is a uv workspace member but
is *not* in `geneweaver-api`'s `[project].dependencies`, and `grep -r geneweaver.tools src/`
returns zero hits.

### The tools-first premise

`docs/tools/TOOLS_BENCHMARKS.md` and `TOOLS_MIGRATION.md` record the state of eleven ported tool
identities — nine in `packages/tools`, plus ABBA and SimilarGenesets in `packages/db`. The nine
package tools are implemented by **ten** `AbstractTool` classes because DBSCAN has default
in-process and legacy-binary variants. **None has a v3 API caller.**

**Group 1 — the port changed the algorithm, and it was benchmarked.** These are the measurable
wins, and all four are unavailable through legacy in this form:

| Tool | What the v3 port changed | Better? | Evidence |
|---|---|---|---|
| **DBSCAN** | in-process scipy+sklearn replaces the C++ binary | **Promising — now the default** | the benchmark reports identical clusters on one real graph and its synthetic sizes, and **3.4× → 61×** speedups; it removes the compiled-binary, subprocess and `ARG_MAX` dependencies. The **6/6 validator covers `BinaryDBSCAN`, not the in-process default**. `BinaryDBSCAN` is retained for exact legacy parity, and the default still needs a non-trivial multi-cluster parity validator |
| **JaccardClustering** | `scipy.cluster.hierarchy.linkage` replaces hand-rolled agglomerative clustering | **Promising** | the benchmark executes **average linkage only** and measures up to **105×** faster, but it does not compare the two returned trees or calculate the documented "max diff 0.0". Its docstring claims complete/single/mcquitty coverage without implementing those legacy methods. *Caveat:* legacy `ward` is non-standard, so scipy's textbook `ward` intentionally differs |
| **HyperGeometric** | exact-integer `math.comb` replaces legacy's incremental-float `combtl` | **Yes — correctness first** | fixes legacy's cross-tail `pval` accumulation bug; legacy's two-tailed p is **wrong on 35/45** validated pairs. Also **1.1–2.9×** faster. Validation **45/45 on all 6 checks** |
| **PhenomeMap** | the scipy `ks_2samp` swap was measured and **reverted** | **Yes, by reverting** | scipy was **slower** (1.3×–11×) *and* changed results (up to ~0.11). The port is now a faithful pure-Python asymptotic KS — faster than both numpy-legacy and scipy — and drops scipy from PhenomeMap entirely. Validation **6/6** |

**Group 2 — faithful refactors onto `AbstractTool`.** No algorithm change, so no performance claim
is made; each is covered by a legacy-parity validation instead. UpSet is a particularly strong
tools-first argument because the deployed legacy app cannot run it:

| Tool | Port status | Legacy-parity validation | Reachable in legacy today? |
|---|---|---|---|
| **BooleanAlgebra** | port of `TOOLBOX/CS_Boolean/service.py` | **3/3 relations** (union / intersection / except) | Yes |
| **Combine** | port of `toolbase.combine_genesets` | **3/3** (gene × gene-set matrix + labels/names) | Yes |
| **BinaryDBSCAN** | exact wrapper around the legacy C++ implementation | **6/6** (encode/gate/decode against the same binary) | Yes |
| **JaccardSimilarity** | coefficient + empirical p-value; `distribution_generator` treated as a separate data-prep step | **all match** — 45/45 coefficients, 15/15 p-values where intersection > 0, 30/30 correctly skipped at intersection 0 | Yes |
| **UpSet** | exclusive-intersection sizes | **2/2 modes** (`include_zeros` off = 5 combos, on = 63) — validated against a *transcription* of py-upset semantics, because the legacy implementation uses pandas' removed `DataFrame.ix` and cannot execute | **No** — `'tools.UpSet'` is commented out of `legacy/tools-worker/tools/celeryapp.py`, `upsetblueprint` is never registered, and the code is py2-era |
| **MSET** | binary wrapper; **fixes** legacy using `group_1_background` for *both* gene lists | **all match**, including verification of that bug fix. Monte Carlo stays in `MSETcpp` | Yes, but see A7 |

HyperGeometric is already in Group 1; like UpSet, its worker module is commented out of legacy's
Celery include list, so the deployed legacy app cannot launch it.

**Group 3 — moved to the db layer, not to `packages/tools`.** G3-763's epic text says these went
to `geneweaver-tools`; they did not.

| Unit | Where it lives | Validation | Notes |
|---|---|---|---|
| **ABBA** | `packages/db/.../abba.py` + `query/abba.py` | **5/5** vs a verbatim transcription of the legacy ABBA SQL | The only tool with an input resolver already written. No endpoint |
| **SimilarGenesets** | `packages/db/.../geneset_jaccard.py` | **none** — only a db unit test (`packages/db/tests/unit/test_geneset_jaccard.py`); no `validate_*.py` exists | Its own docstring says the caller owns the transaction *and* the async execution ("can take minutes on the full database") — and no such caller exists. A natural AsyncTask plugin in its own right |

That is the argument for sequencing tools ahead of UI, and it inverts
`NEW_UI_GAP_AND_PLAN.md` §9, which starts at G3-787→G3-789 (UI shell, auth, typed client).

**Four gaps in the validation set, folded into A8:** the default in-process DBSCAN has benchmark
agreement but no dedicated parity validator; there is no `validate_jaccard_clustering.py` (and the
benchmark executes only `average`); there is no legacy-parity validation for SimilarGenesets; and
PhenomeMap's reported "max score diff 0.0" is **vacuous** — `gene_rank` is uniformly `0.0` on
local, dev and sqa, so the KS term never fires.

### Scope decisions

1. **G3 only.** Epics G3-763, G3-786, and the v3-relevant parts of G3-754.
2. **Tool execution model: AsyncTask — resolved 2026-09-22.** The A1 spike settled it: tools run
   as **plugins inside AsyncTask**, a separate Temporal-backed JAX service. G3-800's "Redis queue +
   `production.result`" design was the wrong answer and is closed as Won't Do. Details in §2;
   consequences throughout §4 and §5.
3. **First phase is the API-only tools spine.** No UI work until the tools API is real.
4. **Legacy's REST API must keep working**, at full surface **including the tool-launch
   endpoints**. No existing ticket covers this.
5. **Un-ported legacy tools stay out of scope** — GeneSetViewer, TricliqueViewer, PhenomeMap
   permutation, FindVariants, similar-variant-set, variant-distance-matrix, NESS — until asked for.
6. **This document makes no Jira changes.** §3 is a set of recommendations to act on.

> ### Conflict between decisions 4 and 5 — flagged, not silently resolved
>
> Full tool-launch compatibility includes `/api/tool/genesetviewer/*`,
> `/api/tool/tricliqueviewer/*` and `/api/tool/findvariants/*` — three families whose tools
> decision 5 puts out of scope. FindVariants additionally traverses a **Neo4J** graph DB that v3
> has no connection to, and has **no legacy worker module at all**, so it is already
> non-functional in legacy.
>
> **Assumption this roadmap proceeds on:** compatibility covers the **7 of 10** tool-launch
> families whose tools are ported — jaccardclustering, jaccardsimilarity, combine, phenomemap,
> booleanalgebra, mset, upset, each with its `byprojects` twin. The other three return a
> documented `501`/`410` with a pointer until those tools are ported. If all ten must work,
> decision 5 has to change and a port workstream for those three re-enters scope.
>
> PhenomeMap still has an internal conflict inside that assumption: its legacy REST contract
> accepts permutation controls, while decision 5 excludes PhenomeMap permutation and the port's
> `PhenomeMapInput` has no permutation fields. Phase E must either define those parameters as
> explicitly unsupported (with a non-2xx response when requested) or bring permutation back into
> scope; silently accepting and ignoring them is not compatibility.

---

## 2. Ground truth (verified 2026-09-21; AsyncTask findings 2026-09-22)

### v3 API surface

- The only state-changing routes: `PUT /genesets/{id}/threshold`, `PUT /genesets/{id}/ontologies`,
  `DELETE /genesets/{id}/ontologies/{ontology_id}`, `PUT /publications/{id}`.
- `controller/batch.py` defines `POST /batch` and `POST /batch/validate` but is **never
  imported** in `controller/api.py`. Its service (`services/parse/batch.py:44-47`) never
  persists and returns a hardcoded `[10], [], []`. `pyproject.toml:75-77` omits it from coverage
  with a TODO.
- `api_router`'s `Security(deps.auth.implicit_scheme)` is **not** auth enforcement —
  `OAuth2ImplicitBearer.__call__` returns `None` unconditionally (`core/security.py:49-54`);
  it exists for Swagger UI. Real auth is per-route (`Security(deps.full_user)` /
  `optional_full_user`).
- **Authorization is inconsistent, not ownership-only.** `schemas/auth.py:8-13` declares
  `AppRoles = {user, curator, admin}`, but `role` is never populated from the token
  (`_process_payload` calls only `_process_email`), so the token-role curator checks at
  `services/geneset.py:498,552` can never be true. `JWT_PERMISSION_PREFIX = "approle"`
  (`core/config_class.py:48`) and `AppRoles.admin` are unused. However, threshold updates already
  embed the authoritative DB checks (`usr_admin > 0` and assigned curation) through
  `query/threshold.py`; ontology writes do not. Publication creation requires authentication but
  no curator/admin role. Phase C must converge these paths on one explicit authorization matrix.
- JWKS is fetched **once, synchronously, at import time** (`core/security.py:85`), with no
  rotation and no retry.
- **Bearer tokens are logged on successful authentication.** `_add_auth_info` stores the raw token
  and `Authorization` header on `UserInternal`, then `logger.info(... {user})` renders that model;
  a debug log also renders the decoded JWT payload (`core/security.py:186,246,261-263`). Remove
  both secret-bearing logs before any production rollout and add a log-capture regression test.
- An **uncommitted working-tree change** adds CORS middleware hardcoded to `localhost:4201`
  (`controller/api.py:38-44`). Local-dev only; must not ship as written.
- **v3 shares legacy's database on dev** — both deployments consume `secretRef: geneweaver-db`
  in the same namespace. v3's pool also puts `public` ahead of `production` in its `search_path`,
  where legacy's omits `public` entirely. This is a deliberate decision as of 2026-09-22; the
  guardrails that replace isolation are in §4.

### Tools

- Nine tools in `packages/tools`: BooleanAlgebra, Combine, DBSCAN, HyperGeometric,
  JaccardClustering, JaccardSimilarity, MSET, PhenomeMap, UpSet. **ABBA and SimilarGenesets went
  to `packages/db`** (`abba.py`, `geneset_jaccard.py`), not to `packages/tools` — G3-763's epic
  text says otherwise.
- `AbstractTool` (`framework/abstract.py:12`) is **synchronous**: `run(ToolInput) -> ToolOutput`.
  No registry, no dispatcher, no status, no persistence, no cancellation.
  `framework/enum.py`'s `WorkflowType{WDL,NEXTFLOW}` is dead code.
- Every tool takes **pre-resolved data** — no tool touches the DB. Nothing assembles those
  inputs; only ABBA has a resolver.
- **Two tools are not reachable through the deployed legacy app.** `'tools.HyperGeometric'` and `'tools.UpSet'`
  are both commented out of `legacy/tools-worker/tools/celeryapp.py`'s `include` list, and
  `upsetblueprint` is never imported or registered in `application.py`. For these two, v3 is not
  an improvement on legacy — it is the only implementation.
- `jaccard_clustering` raises `ImportError` at module level without the `[sklearn]` extra
  (`tool.py:24-32`); the in-process DBSCAN default needs it too.
- Binary paths come from env vars: `GENEWEAVER_BICLIQUE_BINARY` (required for PhenomeMap),
  `GENEWEAVER_BSTRAP_BINARY` (optional bootstrap), `GENEWEAVER_MSET_BINARY`,
  `GENEWEAVER_MSET_BACKGROUND_DIR`, `GENEWEAVER_DBSCAN_BINARY` (optional — in-process is default).
- **This repo contains no execution machinery at all.** No Celery, Redis, broker, scheduler,
  worker or `BackgroundTasks` use anywhere in `src/`, `packages/` or `deploy/`; installed
  `jax-apiutils 0.2.0a6` ships SSE *schemas* (`fastapi/schemas/server_sent_event.py`, the G3-726
  fix) but no task runner. `deploy/k8s` for v3 is **one uvicorn Deployment** — no worker, no
  Redis, no PVC, no CronJob. G3-800's "already-running Redis (`gw-redis:6379`)" belongs to the
  **legacy** stack.
- **That machinery lives in AsyncTask, and it is not ours.**
  `bitbucket.org/jacksonlaboratory/asynctask` v0.6.0a1 is a separate deployed JAX service:
  **Temporal**-backed (`temporalio ^1.5.0`), with its own database (alembic migrations), API
  routers, Dockerfile and skaffold config. It runs analysis work as **plugins**, discovered with
  `importlib.metadata` over the **`jax.ats.plugins`** entry-point group
  (`src/asynctask/plugins/loaders.py`) and validated against one protocol:

  ```python
  @runtime_checkable
  class AsyncTaskPlugin(Protocol[InputType, OutputType]):
      def run(self, input_data: InputType) -> OutputType: ...
  ```

  `AbstractTool.run(tool_input) -> ToolOutput` already satisfies it — the protocol is
  `runtime_checkable`, so conformance turns on the presence of `run`. **No tool code had to
  change.** AsyncTask already hosts sibling plugins: `strain-recommendation`,
  `asynctask-mpd-plugin`, and `geneweaver-boolean-algebra 0.3.0a23` from test-pypi.
- **The integration is a packaging problem, split across two repos.** Monorepo PR #32 declares the
  nine tools under `[project.entry-points."jax.ats.plugins"]`, namespaced under `geneweaver.`
  because AsyncTask's loader raises on duplicate names across *every* installed plugin. Getting
  them to actually run there additionally needs a publish to the private `gcp-dev` index and a
  dependency added on the AsyncTask side — neither of which is a change to this repository.

### Legacy — what v3 has to replace

- **Tool runs:** `POST /run-*` inserts a `production.result` row (`res_runhash` = uuid task id),
  then `celery_app.send_task('tools.<Tool>.<Tool>', task_id=...)`; the client polls
  `GET /<Tool>-status/<task_id>.json`. Results land in `production.result.res_data` **and** as
  `<task_id>.{odemat,el,bic,dot,graphml,json,csv,svg,pdf}` on a **100Gi RWM GCSFuse PVC**
  (`geneweaver-pvc`, mounted at `/var/geneweaver/results`). Soft time limit 900s, single default
  queue, one worker replica.
- **Search:** a Sphinx/Manticore sidecar reindexing **delta every 900s + full at local
  midnight**, plus `production.geneset_search` refreshed by legacy's only CronJob (`30 0 * * *`,
  `America/New_York`). v3 search reads that same materialized view.
- A second, **undeployed** Flask app exists at `legacy/curation-server/` — 17 routes under
  `/curation`, Python-2-era code, in no Dockerfile or manifest.
- **Legacy REST API:** Flask-RESTful, exactly **44 registered routes**
  (`application.py:6049-6383`): 18 reads, 4 state-changing routes, 3 result file/link/status
  routes, and 19 tool-launch routes across 10 families. Most carry `<apikey>` in the URL path,
  but three public reads and tool status do not; several tool launchers contain TODOs instead of
  gene-set access checks. Compatibility therefore needs an explicit security contract, not a
  blind copy of legacy behavior.

---

## 3. Ticket reconciliation — recommendations

No Jira changes were made. These are what to do before work starts. Ticket scope was cross-checked
against repository documentation; the private live Jira pages were not accessible during this
review, so confirm current descriptions, parents and statuses before applying the changes.

| Action | Tickets | Why |
|---|---|---|
| ~~Merge / pick one~~ **Done** | **G3-750** vs **G3-800** | Resolved by the A1 spike. **G3-800 closed as Won't Do (2026-09-22)** with a comment recording the finding and re-homing its still-live requirements (user attribution, diagnosable failures, retention, the legacy status/file contract) onto G3-801. **G3-750 survives**; its first slice is PR #32. |
| **Merge** | **G3-751** into **G3-804** | Both are "build & ship the TOOLBOX binaries". G3-804 also owns the `biclique` SIGTRAP, which is the actual blocker. |
| **Split** | **G3-799** | Its UI result page belongs to the UI phase under the API-only decision. Keep resolver + sync endpoint; move the result page out. |
| **Re-split epics** | **G3-786** | Named "New GeneWeaver UI" but owns nine **API** tickets (792, 793, 795, 796, 798, 799, 800, 801, 804). A separate `v3 API` epic — or moving them under G3-763 — makes the critical path visible in Jira. |
| **Re-parent** | **G3-764**, **G3-777** | v3 search sits in G3-763 while the search UI sits in G3-786; they share one filter foundation. |
| **Note dependency** | **G3-773** → **G3-795** | Score-type validation is explicitly gated on v3 upload existing. |
| **Doc fixes** | — | G3-763 says ABBA/SimilarGenesets went to `packages/tools` (they went to `packages/db`). `TOOLS_MIGRATION.md` §8 quotes "131 of 9,623" where G3-784 measured **63 of 5,319**. `TOOLS_BENCHMARKS.md` overstates DBSCAN/JaccardClustering validation as described in §1, and `scripts/benchmarks/plot_benchmarks.py` **hardcodes** benchmark numbers instead of computing them. `NEW_UI_GAP_AND_PLAN.md` also still says there are no write routes, calls auth an entirely UI-side gap, and assumes the legacy Redis is available to v3. |

---

## 4. Working against the shared dev database — guardrails

> **Decision (2026-09-22):** v3 backend and tools work runs against the **existing** dev database
> — `geneweaver-dev` on `jax-dev-10-guided-jay`, the same one legacy uses. No separate v3 database
> will be provisioned. This section records what that means and the guardrails that stand in for
> isolation.

### What is being accepted

v3's deployment and legacy's consume the **same secret in the same namespace**:
`secretRef: geneweaver-db` at `deploy/k8s/base/deployment.yaml:25-26` and
`legacy/deploy/k8s/base/deployment.yaml:83-84` (plus the tools-worker at `:53-54` and the
search-view CronJob at `:91-92`). They read different key names out of it — legacy
`DB_HOST`/`DB_PORT`/`DB_NAME`/…, v3 `GWDB_*` (`packages/db/.../core/settings_class.py:57-58`) —
but it resolves to one database. That is already true today; it is harmless only because v3 is
effectively read-only.

From A4 onward it stops being read-only:

| Step | Writes landing in legacy's dev data |
|---|---|
| ~~**A4** job model~~ | **No longer applies.** AsyncTask persists run state in *its own* database, so v3 writes no run rows into the shared dev DB at all. This was the sharpest item in this table and the spike removed it — see guardrail 1 |
| **Phase B** | `gs_count` recomputation, `geneset_value` replacement, `gs_status` soft-deletes, metadata edits |
| **Phase B** thresholds | `process_thresholds` **writes** `gsv_in_threshold` — silently, per G3-827 |
| **Phase C** | net-new tables and grants inside schemas legacy owns |
| **Phase E** | `AddGeneSetByUser`, project create, add/remove gene set |

Two properties of dev raise the stakes: it is the **parity baseline** for A2 and A8 (which is what
`legacy/tools-worker/ab/` exists for), and it is **in active use** by curators on
`geneweaver-dev.jax.org`. The instance is also shared with sqa.

### Guardrails

These replace isolation. **Guardrail 7 is now the one that matters most** — guardrail 1 was the
other, and the AsyncTask finding retired it.

1. ~~**Give v3 its own job table.**~~ **Retired by the AsyncTask finding (2026-09-22).** This
   guardrail existed because A4's plan was to write v3 run rows into `production.result`, the
   table legacy's Celery workers write and `/viewStoredResults` reads. AsyncTask owns run state in
   its own database, so **v3 adds no job table and writes no run rows to the shared dev DB** — the
   risk is gone rather than mitigated, which is strictly better.

   Two things survive from it. First, do not *reintroduce* a v3 job table as a convenience cache
   over AsyncTask; there would then be two sources of truth for run state, in the one database
   legacy also reads. Second, the Phase E compatibility contract still needs run artifacts
   addressable as `/api/tool/get/{file,link,status}/<task_id>` — that is now a question about what
   AsyncTask exposes and where its artifacts live, not about a table in this database. Settle it in
   A4.
2. **Put new v3 objects in their own schema** (e.g. `v3`), not in `production`/`extsrc`. Free,
   prevents object-name collisions with legacy's migration series, and makes "what did v3 add?"
   answerable in one query.
3. **Keep v3's migration series separate, and never renumber into legacy's 117–121+.** More
   important now, not less: both series target one database, and legacy's is applied to
   sqa/stage/prod by the standalone repos.
4. **Confirm automated backups and PITR on `jax-dev-10-guided-jay` before the first v3 write**, and
   know the single-table restore path. This is the cheap insurance that a separate database would
   otherwise have provided.
5. **Give v3 a dedicated DB role on the shared database**, granted only what the current phase
   needs, with a `statement_timeout` and a connection cap (the instance is shared with sqa). Start
   without `DELETE` on `production.geneset`; grant it when Phase B's delete endpoint actually
   exists.
6. **Scope development writes to a test allowlist** — a dedicated test user and a known set of
   gene-set IDs. Phase B write testing must not target curator-owned gene sets on dev.
7. **Freeze the parity baseline before the first write.** A2 and A8 compare v3 against legacy *on
   dev*; if v3 mutates dev, the reference and the variable move together. Dump the exact gene sets
   the harness uses — `scripts/validation/validate_abba.py:25` (GS 514) and
   `validate_combine.py:37` (`[514, 515, 648, 664, 32922, 32912, 32408, 34487, 34486, 32556]`),
   plus the fixtures in the other validators — so the baseline survives later drift.
8. **Keep every statement schema-qualified, and land G3-827.** The two pools disagree: legacy sets
   `search_path TO production, extsrc, odestatic` (`legacy/src/geneweaverdb.py:37`), while v3 sets
   `"$user", public, production, extsrc, odestatic, curation` (`src/geneweaver/api/dependencies.py:52`)
   — **`public` first**. G3-827's "the application is not affected" reasoning describes the legacy
   pool and does not transfer. **v3 is not currently exposed** — `packages/db` calls
   `production.process_thresholds(...)` schema-qualified (`query/geneset/write.py:145`, from
   `geneset.py:289`) — but the protection is one qualified string, not the search path. An
   unqualified call added later, or an ad-hoc `psql` session using v3's settings, resolves `public`
   first on SQA/Prod and rewrites `gsv_in_threshold` with the pre-117 rules.
9. **No destructive maintenance from v3.** No `VACUUM FULL`, no `REFRESH MATERIALIZED VIEW`, no
   bulk deletes — the nightly CronJob owns `production.geneset_search`.
10. **Give the curators notice before write-heavy phases**, since dev is in active use.

### Escalation trigger

Revisit and provision a clone of `geneweaver-dev` on the same instance if any of these happen: a
v3 defect corrupts curator-owned data on dev; parity comparisons stop being trustworthy; or tool
runs cause enough contention to affect sqa. Keeping the option costed is why it stays written down
— `gw-schema.dump` at the repo root is a schema-only dump of `geneweaver-dev`, but it is dated
2026-05-28 and predates migrations 117–121, so it would need re-dumping.

### Verify

- A v3 tool run adds **no** rows to `production.result` — now expected by construction,
  since AsyncTask owns run state, so this reads as a regression check on guardrail 1.
- Phase B writes touch only allowlisted gene-set IDs (guardrail 6).
- The frozen parity fixtures still reproduce their recorded metrics (guardrail 7).
- New v3 objects appear only in the `v3` schema (guardrail 2).

---

## 5. Phase A — tools spine (API-only) · the critical path

Each step is verifiable without any UI. A0–A3 are code-only or read-only. Since the A1 spike,
**A4 no longer writes run state into the shared dev database** — AsyncTask owns that — so the
first writes into legacy's dev data now arrive in **Phase B**. The §4 guardrail that still gates
Phase A is **7, the frozen parity baseline**, because A2 and A8 measure against dev.

### A0. Wire the tools package in — **done in PR #32**

`geneweaver-tools[sklearn]` is now in root `pyproject.toml` `[project].dependencies`.
`[tool.uv.sources]` already pinned the name to `packages/tools`, so the lock resolves it
`editable = "packages/tools"` — never the archived PyPI `0.0.5`, which ships the `AbstractTool`
framework only and none of the nine tools. The `sklearn` extra is required, not optional:
`jaccard_clustering/__init__.py` imports `.tool` eagerly and raises `ImportError` without
scipy/scikit-learn.

**The spike narrowed why the API needs this.** Since execution happens in AsyncTask, the API does
not import tools to *run* them — it needs their `ToolInput`/`ToolOutput` schemas to validate
submissions and deserialise results (A5). The environment that must have the tools *installed* is
**AsyncTask's image**, via the publish in A1b. If A5 ends up proxying AsyncTask without touching
the schemas locally, this dependency can be dropped again.

*Verify:* `uv run python -c "from geneweaver.tools.upset import UpSet"` in the API environment.

### A1. Execution-model spike — **done (2026-09-22)**

**Answer: Temporal, via AsyncTask, as an entry-point plugin.** The full finding is in §2. In
short: AsyncTask is a separate deployed service, not a library; its plugin protocol is satisfied by
`AbstractTool` unchanged; and G3-800's Redis design is closed as Won't Do. What *this* repository
owed was the entry-point declaration, delivered in PR #32 with a contract test that mirrors
AsyncTask's protocol locally.

`NEW_UI_GAP_AND_PLAN.md` §6.2 still recommends the Redis queue and should be corrected.

### A1b. Publish and install the plugins — **the real remaining blocker**

Registration does not put the tools in AsyncTask. Three steps, and **two of them are not changes
to this repository** — which makes this the step most likely to stall:

1. **Publish `geneweaver-tools` to the private `gcp-dev` index**, the source AsyncTask uses for
   `strain-recommendation` and `asynctask-mpd-plugin`. This monorepo package is `0.20.0a0`; the
   archived standalone repo's PyPI line ended at `0.0.5`, so the version jump is a release
   decision, not a bump. No publish pipeline for `packages/*` exists in this repo today.
2. **Add `geneweaver-tools[sklearn]` to `asynctask`'s dependencies** (Bitbucket, separate review
   path), and confirm its image can satisfy the extra.
3. **Resolve the BooleanAlgebra duplication.** AsyncTask already installs
   `geneweaver-boolean-algebra 0.3.0a23`, whose GitHub repo is **archived** (last push
   2025-01-15), against `packages/tools/.../boolean_algebra/` which is actively developed.
   Namespacing under `geneweaver.` prevents a *name collision*; it does not decide which
   implementation is authoritative. The archived-versus-maintained asymmetry argues for
   `packages/tools`, but two implementations of one tool would be live until someone decides.

*Verify:* AsyncTask's `load_plugins()` lists the nine `geneweaver.*` plugins in a deployed
environment.

### A2. Input resolvers — G3-798

In `packages/db`. **Promote, don't rewrite**: working legacy SQL transcriptions already exist
inside `scripts/validation/validate_*.py`. Build in readiness order, because three tools are
blocked on data or binaries.

| Order | Tool | Resolver source | Blocked by |
|---|---|---|---|
| 1 | UpSet, HyperGeometric | `validate_upset.py`, `validate_hypergeometric.py` | nothing |
| 2 | Combine, BooleanAlgebra | `TOOLSET_SQL`, `GET_HOMOLOGS_SQL` (`validate_combine.py`, `validate_boolean_algebra.py`) | nothing |
| 3 | DBSCAN (in-process), JaccardClustering | gene symbols per set; similarity matrix | `[sklearn]` extra |
| 4 | JaccardSimilarity | `validate_jaccard_similarity.py` | `extsrc.jaccard_distribution_results` **empty** in current DBs |
| 5 | MSET | two gene lists + background | **A7** |
| 6 | PhenomeMap | gene symbols + `gene_rank` | `biclique` **SIGTRAP**; `gene_rank` uniformly **0.0** on local/dev/sqa |

*Verify:* per-resolver unit tests against a known gene-set fixture, then compare resolver output
against what the legacy worker receives — **on metrics, not raw `ode_gene_id`s**, because dev's
internal ids were remapped in the Dec-2025 reload.

### A3. Vertical slice — G3-799, API half only

One **synchronous** `POST` that resolves inputs, runs UpSet or HyperGeometric in-process and
returns the result. Apply `Security(deps.full_user)` plus the gene-set access gate **now**, so the
authorisation shape is settled before it is copied across the remaining tool endpoints. Write down
the three decisions this exposes: result payload shape, error contract, access gate.

The access gate must be a **single shared dependency/service** used by native and compatibility
routes: resolve the authenticated DB user, reject every unreadable input gene set before doing
expensive work, and distinguish `401` (no/invalid credential), `403` (known user, forbidden), and
`404` (missing resource without leaking private-set existence). Do not copy the legacy tool
launchers' unchecked `TODO` behavior.

One contract detail to settle here, because it is easy to miss: legacy renames the
BooleanAlgebra `Except` relation to **"Symmetric Difference"** at render time
(`booleanalgebrablueprint.py:267-268, 326-327`) rather than computing a fourth relation. The v3
port's three relations are therefore full parity, but the result payload must carry the same
display label or users will see a different word than legacy for the same operation.

*Verify:* `pytest` plus a curl against a local API; the result matches the legacy tool on metrics.

### A4. Integrate with AsyncTask's run model — no longer "build a job model"

The spike changed this step's nature. v3 does **not** build a queue, a worker, a job store or a
job table: AsyncTask owns run state, transitions, retries and persistence in its own database, on
Temporal. What remains is an **integration and contract-mapping** job, and the open questions are
about what AsyncTask already guarantees rather than what we must implement.

**Establish against AsyncTask, by reading its code and API rather than assuming:**

- how a run is submitted and identified, and whether its identifier can be (or be mapped to) a
  legacy-shaped uuid `res_runhash`;
- what it persists and for how long — retention and cleanup ownership;
- its status vocabulary and whether `queued → running → succeeded|failed|cancelled` is atomic,
  with cancellation and timeouts, so a worker death cannot leave a run permanently "running"
  (this was G3-739's failure mode in the Strain Recommender, so it is not hypothetical);
- how it authorises reads — IS-531's "x-on-behalf-of" work and G3-736's ORCID-access bug both sit
  here, and result ownership must be enforced by AsyncTask or by v3 in front of it. A UUID is not
  an authorization control;
- where run **artifacts** live, since the ported tools return data only.

**Decision 4 constrains the mapping.** Full legacy tool-launch compatibility means v3 must serve
`/api/tool/get/status/<task_id>`, `/api/tool/get/file/<apikey>/<task_id>/<file_type>` and
`/api/tool/get/link/...`. Therefore:

- the legacy `res_runhash` uuid must map onto an AsyncTask run id, in a way that survives
  restarts. If AsyncTask's ids are not uuid-shaped, v3 owns a **mapping**, which is a lookup table,
  not a second job store — keep the distinction, per §4 guardrail 1;
- legacy's `production.result` columns still matter for the **dual-run read path**: during cutover,
  legacy's `/viewStoredResults` reads `production.result` and will not see AsyncTask runs. Decide
  deliberately whether that is acceptable (users see v3 runs only in the new UI) or whether v3
  back-fills a row for visibility. The former is simpler and is what guardrail 1 now implies;
- v3 must emit tool result **files** per run (`<task_id>.<ext>`), not only a JSON payload. The
  ported tools return data only, so file rendering is net-new work and belongs here, not in the UI;
- the results-volume question becomes **cutover-blocking** (gap 8 below), and the GCSFuse rule
  applies: generate on local disk, then a single bulk `cp` to the bucket.
- the lifecycle must define atomic `queued → running → succeeded|failed|cancelled` transitions,
  idempotent retry behavior, timeouts, concurrency limits, cancellation, retention/cleanup and
  artifact publication. A worker death must not leave a run permanently "running".
- status, listing, rerun, deletion and artifact download must all enforce result ownership (or an
  explicit curator/admin override); a UUID is not an authorization control.

*Verify:* a submitted run survives an API restart; worker loss and retry cannot execute a
non-idempotent publish twice; a crashing tool yields a failed job with a diagnosable message rather
than a hung "running" row; unauthorized users cannot poll or fetch another user's run; a
legacy-shaped status poll against a v3 run returns the documented compatibility contract.

### A5. Tool run endpoints — G3-801

`POST /api/tools/{tool}`, `GET /api/tools/runs/{id}`, run listing/cancel/delete/rerun, result
download.

**Settle first whether these endpoints proxy AsyncTask or re-expose it.** AsyncTask has its own
API routers, so v3 could forward submissions and status through to it, or present its own surface
over it. Proxying is less code and one source of truth; re-exposing gives control over the legacy
compatibility shape required by Phase E. Either way v3 owns the gene-set **access gate** — a user
must not run a tool over gene sets they cannot read — because only v3 knows GeneWeaver's
permission model.
 Cover all eleven ported tool identities explicitly: nine package tools (ten
`AbstractTool` classes because DBSCAN has two variants) plus the DB-backed ABBA and
SimilarGenesets operations; record any unit intentionally withheld. Expose
`odestatic.tool` and `tool_param` so parameter forms are data-driven rather than nine hand-built
forms. Design the parameter schema so legacy's positional path params — phenomemap has **14** —
map onto it in Phase E without a second parameter model, while rejecting unsupported parameters
rather than silently discarding them. Put per-tool input-size and parameter bounds in this layer
before jobs enter the queue.

### A6. Native binaries — G3-804, with G3-751 merged

⚠️ **The spike moved the target image.** Both tickets describe shipping the TOOLBOX binaries in
"the geneweaver-tools deploy image" (G3-751) or "the API/worker image" (G3-804). Neither is where
the tools now execute: MSET needs `MSETcpp` + `libomp` and PhenomeMap needs `biclique` inside
**AsyncTask's** image, since that is the process that loads the plugins. Both ticket descriptions
need correcting, and the build work lands in a repo this team does not own — the same
cross-repo dependency as A1b, so sequence them together.

**Fix the `biclique` SIGTRAP first**; it blocks PhenomeMap regardless of how the wiring is done.
`TOOLS_MIGRATION.md` §9 notes the recovered binary needs the commented-out linear-search block in
`bigraph.c` rather than POSIX `hsearch`. Then `MSETcpp` + `libomp`. Env-derived paths only —
never a hardcoded `/srv/...` — and **no `|| echo "WARN: ..."` around compile steps**: assert each
binary exists and is executable at image build or startup, so a missing artefact fails the build
rather than the first user request.

### A7. MSET background from the DB — G3-784

Resolve the background at run time as the **full gene space** for the input's id-type and species
(`extsrc.gene`), passed via `ToolInput`. This deletes **300 unique background files duplicated
across two TOOLBOX trees (600 tracked `*BG.txt` files)**, the regeneration job and the
per-environment storage. Both halves are required: DB-resolution alone still rejects Tier-IV
sets, and a full universe alone still goes stale.

This requires a real tool-contract change: `MSETInput` currently carries two **background file
names**, and `MSET` joins them to `GENEWEAVER_MSET_BACKGROUND_DIR`. Change the input to carry the
resolved universes (or a typed resolver result), have the worker write run-scoped local temporary
files for `MSETcpp`, and guarantee cleanup. Passing a DB-derived filename would retain the stale
cache design under a new name.

*Verify:* GS407805 — 63 of 5,319 genes currently out-of-universe — runs clean.

### A8. Parity & benchmark gate

Close the four validation gaps identified in §1:

- add a validator for the **default in-process DBSCAN** against `BinaryDBSCAN`, using graphs that
  produce multiple clusters, border points and noise; the existing 6/6 validator exercises only
  the binary wrapper, while the benchmark's real fixture collapses to one connected cluster;
- add **`validate_jaccard_clustering.py`** covering complete, average, single and mcquitty — today
  the benchmark executes only average and does not compare outputs. Assert/document the
  intentional non-parity of `ward`;
- add a **legacy-parity validation for SimilarGenesets** (`db/geneset_jaccard.py`), which has
  none — only a db unit test;
- re-assess **PhenomeMap**'s "max score diff 0.0", which is vacuous while `gene_rank` is
  uniformly `0.0`; it proves the pipeline matches, not that the KS term does.

Then re-run the full validation suite plus `legacy/tools-worker/ab/` against dev and republish
`docs/tools/TOOLS_BENCHMARKS.md` from **measured** numbers (see the `plot_benchmarks.py` note in
§3). This is what turns "the port is faster" into a claim that survives review.

---

## 6. Phases B–F

### Phase B — gene-set write API (G3-792, G3-793, G3-773, G3-795)

**G3-792 is under-scoped.** `packages/db` has **no** `update_geneset` and **no** `delete_geneset`
at any layer — only `update_date`. Metadata edit and delete are net-new query work, not just
controllers.

Non-negotiables carried over from prior incidents: derive `gs_count` from the rows actually
stored *after* the insert; parameterise every statement; never threshold a binary gene set.
G3-795 must also mount the router and report unresolvable identifiers instead of dropping them.

### Phase C — projects, groups, access model (G3-796 + new)

`packages/db` has `project.py` (5 functions, zero endpoints) but **no `group.py` at all**, though
`core/schema/group.py` defines `Group`/`UserAdminGroup`. Groups are net-new at the db layer.

This phase needs its own decision ticket for the **authorization model**: choose DB-backed roles,
Auth0 claims, or a documented reconciliation rule; then remove the unused alternative. Threshold
updates already use DB-backed `is_curator_or_higher` / `is_assigned_curation` query fragments,
while ontology writes rely on the unpopulated `AppRoles.curator`. Today token-derived curator and
admin roles are unreachable in v3, while legacy has 12 admin routes plus 21 Flask-Admin views.

### Phase D — v3 search (G3-764, G3-777)

Build the shared filter foundation once; both tickets extend it. Two things to fold in:

- dev is **missing migration 116's GIN index** on `production.geneset_search`, so
  `GET /api/genesets/search` sequential-scans ~261k TOASTed rows there. Written up in
  `docs/g3-tickets-to-file.md` ticket 2 and **never filed**.
- v3's freshness is a nightly view refresh against legacy's **900s Sphinx delta** — a parity
  question, not only a performance one.

### Phase E — legacy REST API compatibility (net-new, no tickets exist)

Full surface including tool launch, per decision 4. This is the second-largest workstream after
Phase A and cannot start before A4/A5.

1. **API-key auth path** — the hard prerequisite. v3 has none; `packages/db` already has
   `user.by_api_key` and `user_id_from_api_key` (`db/user.py:29,73`), exposed nowhere. Legacy
   passes the key as a **URL path segment**, so it lands in access logs and browser history:
   reproduce the contract, but scope that dependency to the compat router only and do not extend
   path-segment keys to native v3 routes. Redact the key from application/ingress traces, never
   redirect it into another URL, and publish a migration/deprecation path toward a header-based
   credential. Preserve the three intentionally public read routes only after an explicit data
   exposure review.
2. **18 read endpoints** (`application.py:6052-6325`) — mostly thin wrappers over `packages/db`
   functions that already exist. The response shapes are the work, not the queries.
3. **4 write endpoints** — project create, add/delete geneset-to-project, and
   `POST /api/add/geneset/byuser/<apikey>/`. Depends on Phase B (upload) and Phase C (projects).
4. **3 tool file/status endpoints** — satisfied by the A4 design, but add ownership enforcement to
   status and to the final `/results/<filename>` response; legacy status and static result files
   are reachable without an API key.
5. **7 of 10 tool-launch families + `byprojects` twins** — map legacy's positional params onto
   the A5 parameter model. The other three are blocked by decision 5; see the conflict flag in §1.
6. **Do not reproduce the legacy bugs.** Implement the *intended* contract where legacy's own
   route is broken — these have no working consumers by construction:
   - all `/api/tool/upset/*` — `upsetblueprint` is never imported or registered, so the route
     raises `NameError` at request time;
   - `ToolMSET` — the route exposes `<method>` while the resource method expects
     `numberOfSamples`; even after that keyword mismatch, its four values are positionally
     incompatible with `run_tool_api(apikey, num_samples, geneset_1, geneset_2)`;
   - `ToolJaccardSimilarity` — its resource and URL omit the required `p_Value` argument;
   - the four directly decorated blueprint API routes (PhenomeMap, GeneSetViewer, TricliqueViewer,
     MSET) — their URL rules supply none of the required function arguments, so direct requests
     raise `TypeError`; PhenomeMap additionally ignores the API key and requires a browser session;
   - `ToolTricliqueViewer` — returns a random UUID without inserting or launching a job;
   - the shadowed duplicate `ToolBooleanAlgebra` at `application.py:6255`, unreachable behind
     `:6264`.
7. **Compatibility test suite** — record request/response pairs from legacy on dev for every
   *working* endpoint in scope, then assert v3 reproduces them. For broken endpoints, write the
   intended request/response contract first instead of snapshotting a 500. Include auth/access
   cases and response headers as well as happy-path JSON; without this, "compatible" is an opinion.

### Phase F — UI (G3-787…791, 794, 797, 802, 803)

Deferred by decision 3, plus G3-799's result page. Unchanged from `NEW_UI_GAP_AND_PLAN.md`
§4–§5, except that G3-791 assumes an API-side score-type endpoint that does not exist yet
(gap 16 below).

---

## 7. Backend gap analysis — legacy capability with no v3 ticket

Ordered by how much each blocks switching legacy off.

| # | Gap | Evidence | Blocks cutover? |
|---|---|---|---|
| 1 | **Legacy REST API compatibility** — 44 registered routes; most put the API key in the path | `legacy/src/application.py:6049-6383` | **Yes** (decision 4) |
| 2 | **API-key authentication and compatibility-route hardening in v3** | `db/user.py:29,73` exist; no dependency; legacy has public status/static results and unchecked tool access TODOs | **Yes** — gates 1 |
| 3 | **Curator/admin authorization** | token roles are dead; threshold uses DB role/assignment checks but ontology writes do not | **Yes** |
| 4 | **Curation workflow** — assignments, nominate-public, ready-for-review, mark-reviewed | `application.py:1006-1164`, `curation_assignments.py`; UI plan Phase 4, unticketed | **Yes** |
| 5 | **Publication assignment + stub generators** | `pub_assignments.py`, `publication_generator.py`, `application.py:1193-1654` | **Yes** |
| 6 | **Groups at the db layer** | no `packages/db/.../group.py`; `core/schema/group.py` exists | **Yes** — gates G3-796 |
| 7 | **Geneset update/delete queries** | absent from `packages/db` entirely | **Yes** — gates G3-792 |
| 8 | **Results retention, volume & file outputs** — now partly AsyncTask's: it persists run state, but legacy wrote `<task_id>.*` artifacts to a 100Gi RWM GCSFuse PVC and the compat contract still serves them | legacy `toolbase.py:27`; AsyncTask's artifact story to be established in A4 | **Yes** — promoted by decision 4 |
| 8b | **Tool result-file rendering** — ported tools return data only; legacy emitted `.odemat/.el/.bic/.dot/.graphml/.csv/.svg` per run. Unchanged by the spike: AsyncTask runs the tools, it does not render legacy artifacts | `toolbase.py:27` + per-tool writers; needed by `/api/tool/get/{file,link}` | **Yes** — gates Phase E §4–5 |
| ~~9~~ | ~~**v3 worker / queue / Redis deployment**~~ — **resolved 2026-09-22**: AsyncTask supplies the queue (Temporal), worker and run store. v3 builds none of it | see §2 | No longer applicable |
| 9c | **Cross-repo delivery of the tool plugins** — publishing `geneweaver-tools` to the private `gcp-dev` index and adding it to `asynctask`'s dependencies. No publish pipeline for `packages/*` exists here, and the second half is in a repo this team does not own | §5 A1b; PR #32 covers only the entry-point declaration | **Yes** — gates every tool actually running |
| 9d | **BooleanAlgebra duplication** — AsyncTask installs the archived `geneweaver-boolean-algebra 0.3.0a23` alongside the maintained `packages/tools` implementation; namespacing avoids a collision but not the ambiguity | §5 A1b item 3 | Decide before tool runs ship |
| 9b | **Shared dev-database guardrails** — v3 and legacy share one database by decision (2026-09-22). Scope **reduced** by the spike: A4 no longer writes run rows, so the first writes into legacy's dev data arrive in Phase B. Guardrail 7, the frozen parity baseline, is what still gates Phase A | `deploy/k8s/base/deployment.yaml:25-26` vs `legacy/deploy/k8s/base/deployment.yaml:83-84`; see §4 | **Yes** — gates Phase B, C, E |
| 10 | **Decommission & cutover plan** — URL redirects, `production.result` ownership/schema and writer cutover, artifact migration/retention, dual-run rollback window, client/API-key migration, freezing the legacy release pipeline | nothing in any epic | **Yes** |
| 10b | **Legacy curation-server disposition** — approve/reject/process, stub/comment and curation-admin behavior is outside the main Flask route inventory | 17 routes in `legacy/curation-server/curation_server.py:1155-1171`; app appears undeployed | Decide **port vs retire** before cutover |
| 11 | **Notifications & messaging** | `core/schema/messages.py` + `api/schemas/messages.py` exist; no db, no endpoints; legacy `notifications.py` + 7 routes | No |
| 12 | **Account settings** — password change/reset, API-key generation, notification prefs, annotator choice | `application.py:2704-2758, 5778-5817` | No |
| 13 | **Exports** — batch `.gw`, OmicsSoft, HBA converter, Jaccard gene list, `downloadResult` (SVG→PNG/PDF) | `application.py:2805, 4327-4494`, `export_batch.py` | No |
| 14 | **Geneset overlap / Venn + Find Similar Genesets** | `application.py:3565, 4196`; `db/geneset_jaccard.py` has no caller and its docstring says the caller owns async execution — a candidate for an AsyncTask plugin of its own, since it "can take minutes on the full database" | No |
| 15 | **Ontology browsing, tree & annotator** | `db/ontology.py` `get_ontology_dbs` / `by_ontology_db` unexposed; `application.py:1873-2134`; `annotator.py` (NCBO + Monarch). G3-793 covers annotation *writes* only; the NCBO key is still hardcoded pending **G3-770** | No |
| 16 | **Reference-data endpoints** — score types (`odestatic`) and gene id-types (`gene.id_types`) | G3-791 assumes an endpoint that does not exist; id-types are needed by upload and the detail-page ID selector | No |
| 17 | **Large-geneset upload job** (`LargeGenesetUpload`) | `uploadfiles.py:486` → `ProcessLargeGeneset.py`; absent from `TOOLS_MIGRATION.md` and from G3-795 | No |
| 18 | **Un-ported tools** — GeneSetViewer, TricliqueViewer, PhenomeMap permutation, FindVariants (**Neo4J**, no legacy worker module), similar-variant-set, variant-distance-matrix, NESS | triaged under G3-752 (Done); "port or retire" has **no ticket** | **Out of scope** (decision 5) — see the §1 conflict flag |
| 19 | **`packages/db/aio` is unused by production** — 10 async modules are exported and unit-tested, but the API uses sync cursors and no production caller uses them | adopt or delete; it silently diverges from the sync modules today | No |
| 20 | **Dead/duplicate code in `src/`** — `services/batch.py` (imported by nothing), `services/pubmeds.py` (empty), `api/schemas/score.py` + `messages.py` duplicating `core`, `tests/services/parse/batch/test_parse.py` (no tests), `framework/enum.py` | cheap cleanup, do alongside Phase B | No |
| 21 | **Auth robustness and secret-safe logging** — JWKS fetched once at import with no rotation/retry; successful auth logs `UserInternal` containing the bearer token; decoded payload logged at debug; uncommitted localhost-only CORS config | `core/security.py:85,186,246,261-263`; `controller/api.py:38-44` | **Before any prod rollout** |
| 22 | **Tool workload guardrails** — per-tool input-size limits belong in v3's submission layer (A5); queue quotas, cancellation and retention are now **AsyncTask's**, and must be confirmed against it rather than assumed | `AbstractTool` is sync-only; legacy's global 900s limit was the only guard | **Before exposing tool submission** |

Tracked separately on G3-754 and not part of this roadmap: **G3-761** (rotate the leaked Auth0
secret), **G3-770** (NCBO key), **G3-824** (12 admin routes return 500 instead of Forbidden),
**G3-827** (stale `public.process_thresholds` on Prod/SQA), **G3-785** (in-threshold count in
search results).

---

## 8. Verification

- **Per step:** the *Verify* line in §5. Lint with `ruff src tests --fix` and `black src tests`;
  test with `pytest tests --cov=geneweaver.api`. Package suites run per `packages/*/tests/unit`.
- **Tools correctness** — the existing harness, against the seeded local Postgres on
  `127.0.0.1:5433` (`geneweaver-dev` / `localdev`) with locally built binaries:

  ```bash
  for v in abba dbscan hypergeometric phenomemap boolean_algebra \
           combine jaccard_similarity upset mset; do
    uv run --extra sklearn --project packages/tools python scripts/validation/validate_$v.py
  done
  ```

  The existing `validate_dbscan.py` covers `BinaryDBSCAN`, not the default in-process class. Add a
  dedicated default-DBSCAN parity validator and `validate_jaccard_clustering.py`. All applicable
  validators must pass before an endpoint exposes that tool.
- **Legacy parity on real data:** `legacy/tools-worker/ab/` against dev — compare **metrics, not
  raw `ode_gene_id`s**.
- **Benchmarks:** re-run `scripts/benchmarks/bench_*.py` and regenerate `docs/tools/img/` from
  measured values.
- **End-to-end, no UI:** `POST /api/tools/{tool}` → poll `GET /api/tools/runs/{id}` → compare the
  payload against the legacy run for the same gene sets. Endpoints must appear in
  `/api/openapi.json`; `tests/controllers/test_api_standards.py` already enforces the conventions.
- **Legacy API compatibility:** capture request/response pairs from legacy on dev for every
  working endpoint in Phase E scope and assert v3 reproduces them. For legacy-broken endpoints,
  assert the written intended contract instead of preserving a 500. Include unauthenticated,
  unauthorized/cross-user, malformed-input and negative out-of-scope tool cases; the latter must
  return the documented `501`/`410` rather than a 500.
- **Shared-database guardrails (§4):** a v3 tool run adds no rows to `production.result`; Phase B
  writes touch only allowlisted gene-set IDs; the frozen parity fixtures still reproduce their
  recorded metrics; new v3 objects appear only in the `v3` schema.
- **Deployed check:** `kubectl exec` works on dev and sqa; stage and prod need an image pull.

---

## 9. What this roadmap does not decide

- Whether `gene_rank` and `extsrc.jaccard_distribution_results` are ever populated in prod. Both
  are empty or zero on local, dev and sqa, which makes PhenomeMap's KS term and
  JaccardSimilarity's p-value inert. Confirm with the team before building the dependent
  resolvers (A2 steps 4 and 6).
- The product questions inside G3-764 — OR-across-score-types semantics, and whether thresholded
  results replace or are prioritised above unfiltered ones. A membership/threshold rule change is
  a semantics decision for the curation scientist, not a cleanup.
- Whether the three out-of-scope tool-launch families are genuinely droppable (§1 conflict flag).
- How the legacy PhenomeMap permutation parameters behave while permutation remains out of scope:
  reject non-default requests, remove the family from the compatibility claim, or port the feature.
- Whether existing result rows/artifacts have a retention or compliance obligation. The
  concurrent-write half of this question is **settled**: AsyncTask owns run state, so no v3 worker
  writes `production.result`. What remains is whether legacy's `/viewStoredResults` must show v3
  runs during dual run — see A4.
- What AsyncTask actually guarantees about status transitions, cancellation, retention, artifact
  storage and result authorisation. A4 must establish these from its code and API; G3-736 (ORCID
  users could not access runs) and G3-739 (runs spinning forever after failure) are evidence that
  they cannot be assumed.
- Who owns the cross-repo half of A1b — the `gcp-dev` publish and the `asynctask` dependency —
  and whether this team can merge in that repo or needs another team to.
