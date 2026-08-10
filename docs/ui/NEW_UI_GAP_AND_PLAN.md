# New GeneWeaver UI — Gap Analysis & Implementation Plan

> Comparison of the **legacy** GeneWeaver web app (`legacy/` — Flask + Jinja + Celery) against
> the **new** UI (`ui/` — Angular 18 / Nx, served at `/next`), and the plan to close the gap.
> The new UI is currently an early **read-only search experiment**; most of the legacy product
> is not yet built. **Last updated:** 2026-08-10
>
> **Status:** this roadmap is now broken into tracked work under epic
> [G3-786](https://jacksonlaboratory.atlassian.net/browse/G3-786) — see §9 for the story map.
> Phases 0–3 are filed; Phases 4–5 remain documented here only.

---

## 1. Current state of the new UI

Implemented today (Angular 18 / Nx, PrimeNG + Tailwind):

| Route | Component | What works |
|---|---|---|
| `/`, `/home`, `/search` | `HomeComponent` | Free-text gene-set search → results table (`SearchBarComponent`, `GeneSetListComponent`) |
| `/geneset/:id` | `GeneSetComponent` | Read-only gene-set detail: metadata, publication, gene list with ID-type selector, ontology tags, CSV/JSON export, "view legacy page" link |

API calls made: `GET /genesets/search`, `/genesets/{id}`, `/genesets/{id}/publication`, `/genesets/{id}/ontologies`, `/genesets/{id}/values`.

**Not present at all:** global nav/app-shell, authentication, gene-set management/editing, upload, projects, groups, **analysis tools**, results, curation, publications workflow, notifications, account settings, admin, info/help pages, advanced search.

Known structural shortcuts to address: no service layer — each component builds its own
`ApiBaseService` from `jax-apiutils` and issues raw path strings; no auth service, guard or
interceptor (auth0 config sits unused in the environment files); score-type map hard-coded in
`geneset.component.ts`; the one feature flag (`geneSetDetailsPage`) is unused.

*Fixed since the first version of this document:* the API base URL is no longer hard-coded — it
comes from `environment.urls.geneWeaverApi`, with per-cluster environment files (G3-756).

---

## 2. Legacy feature surface (the target)

Grouped from the legacy Flask routes/templates. Top-level nav: **Manage GeneSets**, **Curation**, **Analyze GeneSets**, plus search, notifications, help, account.

A. Authentication & account (login/SSO, register, password reset, account settings, API keys)
B. Search & discovery (faceted search: genesets/genes/abstracts/ontologies, suggestions, similar gene sets, overlap viewer)
C. Gene-set view **and edit** (details, edit metadata, edit gene values, threshold setting, ontology/publication annotation, delete, nominate public)
D. Upload & creation (single upload, batch `.gw` upload, ID transpose)
E. Projects (create/rename/delete/share/star, add/remove gene sets)
F. Groups & collaboration (create/edit groups, membership, public groups, sharing)
G. **Analysis tools** + `/analyze` launcher + emphasis genes
H. Curation & publications (curation tasks, publication assignment & review workflow, PubMed search/assign)
I. Results management (list, status polling, download, rerun, delete)
J. Export & format conversion (CSV, batch `.gw`, OmicsSoft, HBA converter)
K. Notifications & messaging
L. Admin (usage stats, server-side DB viewers, record edit/add/delete)
M. Public/info pages (help, about, data, datasources, privacy, usage, funding)

### Analysis tools — migration status
The library port (`packages/tools/` + `db/abba.py`) covers **9 + ABBA**:

| Migrated to `packages/tools` | Registered in legacy but **NOT** migrated |
|---|---|
| BooleanAlgebra, Combine, DBSCAN, HyperGeometric, JaccardClustering, JaccardSimilarity, MSET, PhenomeMap, UpSet, (ABBA in `db/`) | GeneSetViewer, TricliqueViewer, NetworkSimilarity, NESS, FindVariants, SimilarGenesets |

---

## 3. Gap analysis

Status legend: ✅ done · 🟡 partial · ❌ missing.

| # | Area | Legacy | New UI | Status | Backend dependency |
|---|---|---|---|---|---|
| B1 | Free-text gene-set search | ✅ | ✅ | ✅ | `genesets/search` exists |
| B2 | Faceted search (genes/abstracts/ontologies), suggestions, pagination | ✅ | basic text only | 🟡 | `search` controller — extend |
| B3 | Similar gene sets / overlap viewer | ✅ | — | ❌ | new endpoints + viz |
| C1 | Gene-set detail (read) | ✅ | ✅ | ✅ | exists |
| C2 | Edit gene-set metadata / genes / threshold / annotations / delete | ✅ | — | ❌ | **write endpoints (none today)** |
| A | Auth: login/SSO, account settings, API keys | ✅ | — | ❌ | **UI-side gap only** — the API already enforces per-endpoint (`Security(deps.full_user)`) |
| D | Upload: single + batch `.gw`, ID transpose | ✅ | — | ❌ | `batch` controller is a stub **and is not mounted** in `controller/api.py` |
| E | Projects | ✅ | — | ❌ | **project endpoints (none)**; `production.project` exists |
| F | Groups & sharing | ✅ | — | ❌ | group endpoints (none) |
| G | **Analysis tools + launcher + results** | ✅ (13 tools) | — | ❌ | **tools endpoints + job model (none)** — see §6 |
| H | Curation & publication workflow | ✅ | — | ❌ | curation endpoints (none) |
| I | Results (list/status/download/rerun) | ✅ | — | ❌ | result/job model (none); `production.result` exists |
| J | Export: batch/OmicsSoft/HBA | ✅ | geneset CSV/JSON only | 🟡 | export endpoints |
| K | Notifications & messaging | ✅ | — | ❌ | notification endpoints |
| L | Admin | ✅ | — | ❌ | admin endpoints |
| M | Info/help pages | ✅ | — | ❌ | static (no backend) |

**Bottom line:** ~2 of ~15 areas implemented (search + read-only detail). The two largest missing products are **analysis tools** (G/I, the core scientific value) and **gene-set management/upload/projects** (C2/D/E). Most areas are blocked on **backend endpoints that don't exist yet** (the API today mounts only `genesets`, `genes`, `publications`, `species`, `search` and
`monitors` — `batch.py` exists but is neither finished nor registered).

---

## 4. Cross-cutting foundations (do first — everything depends on these)

These aren't user features but are prerequisites the current code lacks:

1. **App shell & navigation** — persistent header/nav matching the legacy IA (Manage GeneSets / Analyze / Curation / account / notifications), router layout, breadcrumbs, responsive sidenav. Today there is no nav at all.
2. **Authentication** — auth0 integration (login, token attach via HTTP interceptor, route guards, logout, account menu). The API *does* enforce auth per-endpoint already (`Auth0(auto_error=False)` in `dependencies.py`, with `Security(deps.full_user)` on protected routes and `optional_full_user` where anonymous access is allowed) — the gap is entirely on the UI side. Required before any per-user feature (projects, upload, tools, curation).
3. **API service layer** — replace in-component HTTP + hard-coded base URL with generated/typed services and an env-driven base URL + auth interceptor. Consider generating a client from the API's OpenAPI (`/api/openapi.json`).
4. ~~**Environment config** — move the API base URL into `environment.*.ts`; make `localhost` a real config, not a hand-edit.~~ **Done (G3-756).**
5. **Shared UI kit & state** — a "selection basket" of gene sets (the legacy *project/analyze* concept) shared across pages; toast/error handling; loading/skeleton conventions; reusable tables, tag components (species/tier/ontology already exist — generalize).
6. **Reference data from API** — species and score-type maps are hard-coded client-side; source them from the API (`species` exists).

---

## 5. Phased plan

Each phase is shippable and ordered by dependency. Backend work is called out because most phases are blocked on it.

### Phase 0 — Foundations (cross-cutting §4)
App shell + nav, auth0 login + guards + token interceptor, API service layer + env-driven base URL, selection-basket state, toast/error conventions.
**Exit:** a logged-in user sees a nav shell; existing search/detail pages work through the new service layer and respect auth.

### Phase 1 — Gene-set management (read → write)
Backend: write endpoints for edit metadata / edit gene values / threshold / delete / annotations.
UI: "My Gene Sets" list, edit pages, interactive threshold setter, annotation editor, delete.
**Exit:** a user can manage their own gene sets end-to-end.

### Phase 2 — Upload & projects
Backend: finish `batch` upload (single + `.gw`), ID transpose; project CRUD + add/remove gene sets + sharing; group CRUD.
UI: upload wizard (single + batch), Projects page, group management, sharing modals.
**Exit:** a user can create gene sets and organize them into projects/groups.

### Phase 3 — Analysis tools (the core) — see §6 for the deep plan
Backend: tool input resolvers in `db`, async job model on the running Redis, `POST /tools/{tool}` + `GET /tools/runs/{id}`.
UI: `/analyze` launcher (pick gene sets from basket + per-tool params), run/status polling, **per-tool result visualizations**, results list + rerun + download.
**Exit:** a user can run the migrated tools from the UI and view results — the legacy "Analyze" experience.

### Phase 4 — Curation & publications
Backend + UI for curation tasks, publication assignment/review workflow, PubMed search/assign.
**Exit:** curators can work in the new UI.

### Phase 5 — Periphery
Notifications/messaging, account settings + API keys, advanced/faceted search, similar-gene-sets & overlap viewer, extra exports (OmicsSoft/HBA), info/help pages, admin.

---

## 6. Analysis-tools deep plan (Phase 3 detail)

This is the heaviest area and has its own layered breakdown (the pure tools take a fully-built input; DB access and execution are not yet wired anywhere).

**6.1 Data-layer input resolvers (`packages/db`)** — one per tool, reproducing the legacy SQL; only ABBA exists today. Transcriptions already live inside `scripts/validation/validate_*.py` and can be promoted:
- Combine/Jaccard* → `TOOLSET_SQL` (membership, homology pairs, labels) + pairwise counts; JaccardSimilarity also needs `jaccard_distribution_results` (⚠️ empty in current DBs).
- BooleanAlgebra → `GET_HOMOLOGS_SQL`. DBSCAN/UpSet/PhenomeMap → gene symbols per set (+ gene ranks for PhenomeMap, ⚠️ uniformly `0.0` in local/dev/sqa). MSET → two gene lists + background files.

**6.2 Execution + job model (API)** — async required (tools run seconds→minutes). Recommended: a task queue on the **already-running Redis** (`gw-redis:6379`) with `production.result` (or a new table) as the job store keyed by a run hash, mirroring legacy (`res_status/res_data/res_completed/usr_id/gs_ids`).

**6.3 API endpoints** — `POST /api/tools/{tool}` (validate params → resolve inputs → enqueue → return run id); `GET /api/tools/runs/{id}` (status + result); optionally expose `odestatic.tool`/`tool_param` so the UI renders parameter forms dynamically. Enforce auth0 user + gene-set group-access gate.

**6.4 UI** — `/analyze` launcher (basket + per-tool param forms), run/status polling, results list (rerun/download), and **per-tool visualizations** (net-new — the pure tools dropped all legacy SVG/HTML): Venn/circle (Boolean, JaccardSimilarity), dendrogram (JaccardClustering), cluster view (DBSCAN), UpSet plot, PhenomeMap hierarchy graph, MSET histogram.

**6.5 Runtime/packaging** — DBSCAN default is in-process (no binary). PhenomeMap needs the `biclique` binary (**currently SIGTRAPs — bug to fix first**); MSET needs `MSETcpp` + libomp + background-universe files. Decide how binaries ship in the API/worker image.

**Suggested first vertical slice:** wire **one in-process tool** (UpSet or HyperGeometric — no binary, fast) end-to-end (resolver → sync endpoint → minimal result page) to prove the pattern before adding the Redis worker and fanning out.

---

## 7. Risks, decisions & open questions

- **Backend is the critical path.** Most UI areas are blocked on endpoints that don't exist; UI and API work must be planned together, not UI-first.
- **Execution model decision** (Phase 3): full task queue vs. hybrid (BackgroundTasks for cheap tools, queue for heavy). Redis already running suggests a queue was intended.
- **Visualizations are real frontend work** — the ported tools intentionally return data only; every tool's chart is net-new in Angular.
- **Inert data:** `gene_rank` (PhenomeMap KS) and `jaccard_distribution_results` (JaccardSimilarity p-value) are empty/zero across local/dev/sqa — confirm whether they're ever populated before investing in those result views.
- **biclique SIGTRAP** blocks PhenomeMap regardless of wiring.
- **Un-migrated tools** (GeneSetViewer, TricliqueViewer, NetworkSimilarity, NESS, FindVariants, SimilarGenesets): decide scope — port or drop.
- **Auth scope:** does the new UI need full SSO + account management parity, or is read-only public browsing acceptable for an initial public launch?

---

## 8. Quick reference — what to build next (smallest useful increments)

1. Foundations: app-shell + nav, auth0 login + interceptor + guards, service layer (env-driven API base is done).
2. "My Gene Sets" list (read) — reuses existing detail page; first authenticated feature.
3. One tool vertical slice (UpSet/HyperGeometric) end-to-end to prove the tools pattern.
4. Gene-set edit + upload.
5. Projects + analyze launcher over the basket; then fan out the remaining tools + result views.

---

## 9. Story map

Phases 0–3 are tracked under epic **[G3-786](https://jacksonlaboratory.atlassian.net/browse/G3-786)
— New GeneWeaver UI: feature parity with the legacy app**. Phases 4–5 are documented in §5 but
not yet broken into stories.

| Phase | Story | Covers |
|---|---|---|
| 0 | [G3-787](https://jacksonlaboratory.atlassian.net/browse/G3-787) — app shell & primary navigation | §4.1 |
| 0 | [G3-788](https://jacksonlaboratory.atlassian.net/browse/G3-788) — Auth0 login, token interceptor, route guards | §4.2 |
| 0 | [G3-789](https://jacksonlaboratory.atlassian.net/browse/G3-789) — typed API service layer from OpenAPI | §4.3 |
| 0 | [G3-790](https://jacksonlaboratory.atlassian.net/browse/G3-790) — selection basket + error/loading conventions | §4.5 |
| 0 | [G3-791](https://jacksonlaboratory.atlassian.net/browse/G3-791) — species & score-type reference data from the API | §4.6 |
| 1 | [G3-792](https://jacksonlaboratory.atlassian.net/browse/G3-792) — API: gene-set write endpoints | §3 C2 |
| 1 | [G3-793](https://jacksonlaboratory.atlassian.net/browse/G3-793) — API: annotation & publication endpoints | §3 C2 |
| 1 | [G3-794](https://jacksonlaboratory.atlassian.net/browse/G3-794) — UI: "My Gene Sets" + edit experience | §5 P1 |
| 2 | [G3-795](https://jacksonlaboratory.atlassian.net/browse/G3-795) — API: batch controller (upload, `.gw`, transpose) | §3 D |
| 2 | [G3-796](https://jacksonlaboratory.atlassian.net/browse/G3-796) — API: projects & groups, sharing | §3 E, F |
| 2 | [G3-797](https://jacksonlaboratory.atlassian.net/browse/G3-797) — UI: upload wizard, projects, groups | §5 P2 |
| 3 | [G3-798](https://jacksonlaboratory.atlassian.net/browse/G3-798) — `packages/db`: tool input resolvers | §6.1 |
| 3 | [G3-799](https://jacksonlaboratory.atlassian.net/browse/G3-799) — **vertical slice**: one in-process tool end-to-end | §6 |
| 3 | [G3-800](https://jacksonlaboratory.atlassian.net/browse/G3-800) — API: async job model + Redis queue | §6.2 |
| 3 | [G3-801](https://jacksonlaboratory.atlassian.net/browse/G3-801) — API: tool run endpoints | §6.3 |
| 3 | [G3-802](https://jacksonlaboratory.atlassian.net/browse/G3-802) — UI: `/analyze` launcher + results management | §6.4 |
| 3 | [G3-803](https://jacksonlaboratory.atlassian.net/browse/G3-803) — UI: per-tool result visualisations | §6.4 |
| 3 | [G3-804](https://jacksonlaboratory.atlassian.net/browse/G3-804) — tool runtime & binary packaging (incl. `biclique` SIGTRAP) | §6.5 |

Start with G3-787 → G3-789 (nothing else can be built cleanly without them), then G3-799 as the
earliest demonstrable end-to-end capability.
