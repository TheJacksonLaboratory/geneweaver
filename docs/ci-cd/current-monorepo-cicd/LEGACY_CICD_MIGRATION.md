# Legacy CI/CD Migration — Findings & Plan

> **Scope:** Make the `legacy/` component's CI/CD (GitHub Actions) reflect the proven
> `geneweaver-api` model, and finish consolidating all GeneWeaver repos into this
> monorepo so it can replace them.
>
> **Branch:** `G3-748-finish-migration-of-geneweaver-to-monorepo`
> **Status:** ✅ **LEGACY CI/CD RE-INTRODUCED (2026-07-06).** The 2026-06-03 "drop legacy CI/CD"
> decision was reversed once it was clear the legacy Flask app must keep running in the monorepo
> alongside — and through the switch to — the V3 platform. Legacy now has both
> `legacy-pull_requests.yml` (build+deploy to **dev**) and `legacy-release.yml` (**SQA→Stage→Prod**),
> plus tools-worker fixes that make the TOOLBOX tools actually run in the container, and a dev↔sqa
> A/B harness. The API + UI pipelines from 2026-06-03 remain. See the **2026-07-06** log entry for
> the current state. (Earlier legacy sections are retained as history.)
> **Last updated:** 2026-07-06

---

## 1. Repositories in play

Three repos sit side by side in `/Users/elkasb/git/`:

| Repo | Remote | Role |
|---|---|---|
| `geneweaver` | `github.com/TheJacksonLaboratory/geneweaver` (branch `G3-748-finish-migration-of-geneweaver-to-monorepo`) | **The monorepo** — consolidation target |
| `geneweaver-api` | `github.com/TheJacksonLaboratory/geneweaver-api` (`main`) | **Currently-deployed** backend; canonical CI/CD model |
| `geneweaver-ui` | `bitbucket.org/jacksonlaboratory/geneweaver-ui` (`main`) | Angular/Nx frontend; deployed via **Bitbucket Pipelines** |

## 2. Monorepo layout (current)

```
geneweaver/                     ← uv workspace, builds as "geneweaver-api" v0.20.0a0
├── src/geneweaver/api/         ← the API (was geneweaver-api repo)
├── packages/
│   ├── core/                   ← geneweaver-core   (was its own PyPI lib)
│   ├── db/                     ← geneweaver-db      (was its own PyPI lib)
│   └── client/                 ← geneweaver-client  (was its own PyPI lib)
├── ui/                         ← the UI (was geneweaver-ui / Bitbucket)
│                                  — still carries bitbucket-pipelines.yml + own skaffold.yaml
├── legacy/                     ← OLD GeneWeaver platform (Flask) "geneweaver-legacy" v1.6.0
│   └── .github/                ← ⚠️ NESTED .github — does NOT run on GitHub
├── .github/workflows/          ← the real monorepo CI/CD (API + packages only)
├── skaffold.yaml               ← builds image "geneweaver-api"
└── deploy/k8s/overlays/        ← 4 GKE environments
```

`legacy/` is the GW1/GW2 Flask application: `application.py`, `geneweaverdb.py`, the
curation server, `src/tools/*blueprint.py` (Jaccard, ABBA, boolean algebra, DBSCAN,
gene set viewer, etc.), `migration/`, and `tests/`.
Stack: **Poetry, Python 3.9, Flask + gunicorn + Celery + Sphinx search**.

## 3. CI/CD models compared

All three deploy to the **same four GKE targets** via skaffold kustomize profiles:
`jax-cluster-dev-10--dev`, `--sqa`, `jax-cluster-prod-10--stage`, `--prod`.

### geneweaver-api (the model to copy)
- `pull_requests.yml`: format-lint → check-coverage → test (py3.10/3.11 matrix) → build (dev image repo) → deploy **dev**
- `release.yml` (triggers on `pyproject.toml` version bump): format-lint → check-coverage → test → version-check → build → deploy **sqa** → (full release only) **stage** → **prod** → GitHub release draft
- Reusable actions: `_format-lint-action.yml`, `_run-tests-action.yml`, `_check-coverage-action.yml`, `_skaffold-build-k8s.yml`, `_skaffold-deploy-k8s.yml`

### Monorepo root `.github/workflows/`
An **evolved superset** of the api model: adds multi-package version-sync verification
(`packages/*` must match root) and a `build-and-publish` job that `uv build`s every
package and publishes to PyPI, then runs the same skaffold build → sqa → stage → prod chain.
**But it only knows about the API** (`coverage-module: geneweaver.api`, root `skaffold.yaml`
→ image `geneweaver-api`). It does **not** build, test, or deploy `legacy/` or `ui/`.

### geneweaver-ui (Bitbucket)
`bitbucket-pipelines.yml`: code-integrity (npm lint + test) → build artifacts →
GCS-bucket deploy + skaffold to dev/sqa/stage/prod.

## 4. Core findings (the problems to fix)

1. **Legacy CI is inert.** GitHub Actions only executes workflows in the **repo-root**
   `.github/workflows/`. The `legacy/.github/` tree (workflows + `disabled_workflows/`)
   is leftover from when legacy was its own repo and **will never run** in the monorepo.
   Legacy currently has zero functioning CI/CD.

2. **Even if it ran, it's stubbed.** `legacy/.github/workflows/release.yml` and
   `pull_requests.yml` have format-lint, coverage, and test jobs **commented out**
   (`# TODO: Uncomment when we have Formatting, Linting, Tests`). The `build` job depends
   only on `version` — no quality gates. The copied `_check-coverage-action` is wired to
   `coverage-module: geneweaver.api`, which is **wrong** for legacy (a `src/`-rooted Flask
   app, not the `geneweaver.api` module).

3. **Root workflow ignores legacy and ui.** Consolidation is structurally done (directories
   present) but CI/CD only covers the API + Python packages.

4. **Good news.** `_skaffold-build-k8s.yml` and `_skaffold-deploy-k8s.yml` are
   **byte-identical** between legacy and api, and legacy already has a working
   `skaffold.yaml` (image `geneweaver-legacy`), a `Dockerfile`, and all four
   `deploy/k8s/overlays/`. The only missing capability is targeting a subdirectory's
   skaffold file from the reusable actions.

## 5. Recommended plan

**Recommendation:** keep **legacy as a separately-built/deployed image with its own
root-level workflows**, not folded into the API's jobs. Legacy is a different stack
(Poetry/Flask/Py3.9/gunicorn), a different image (`geneweaver-legacy`), and an independent
version (`1.6.0`) that should not be coupled to the API's uv/PyPI publish or `0.20.x` gate.

### Phase A — Make legacy CI reflect the api CI (in the monorepo root)
- **A1.** Delete the dead `legacy/.github/` tree (workflows + disabled_workflows).
- **A2.** Add a `working-directory` / `skaffold-file` input to the reusable skaffold actions
  so they can target `legacy/` (`skaffold build -f legacy/skaffold.yaml`); name the legacy
  build artifact distinctly (e.g. `build-artifact-json-legacy`) to avoid collision with the API.
- **A3.** Add two root-level legacy workflows, path-filtered to `legacy/**`:
  - `legacy-pull_requests.yml` — PR: format-lint → test → build (dev repo) → deploy `--dev`.
  - `legacy-release.yml` — push on `legacy/pyproject.toml`: version-detect (legacy's own
    Poetry version) → build → deploy sqa → stage → prod.
- **A4.** Fix legacy coverage/test wiring (point coverage at legacy `src/`, confirm
  `legacy/tests` passes on Py3.9) before re-enabling those gates; ship build+deploy first
  if tests aren't green yet.

### Phase B — Finish consolidation so the monorepo replaces every repo
- **B5.** Migrate the UI off Bitbucket: translate `ui/bitbucket-pipelines.yml` into root
  `ui-pull_requests.yml` / `ui-release.yml` (path-filtered to `ui/**`) using `ui/skaffold.yaml`.
- **B6.** Recreate GCP secrets/vars + GitHub Environments on the monorepo repo
  (`GCLOUD_REGISTRY_SA_KEY`, `GCLOUD_CLUSTER_SA_KEY`, `CLUSTER_NAME/REGION/PROJECT`,
  the four `jax-cluster-*` environments).
- **B7.** Cut over deployments to the monorepo, then archive old repos (`geneweaver-api`,
  `geneweaver-core/db/client`, and Bitbucket `geneweaver-ui` after a final mirror).
  Update `Repository` URLs in `pyproject.toml` (root still points at `geneweaver-api`).
- **B8.** Land all of it on `G3-748-finish-migration-of-geneweaver-to-monorepo`.

## 6. Open decisions
- **Separate vs unified deploy:** legacy gets its own version/release cadence and image
  (recommended), or one platform release builds & deploys API + legacy + UI together.
- **Legacy test gate timing:** does `legacy/tests` pass on Py3.9 today? Determines whether
  the test gate goes in now or as a fast-follow.

---

## Session log

### 2026-06-02 — Research session
- Mapped all three repos (`geneweaver`, `geneweaver-api`, `geneweaver-ui`) and their CI/CD.
- Read and compared root, legacy, and api workflows + reusable actions, skaffold configs,
  Dockerfiles, deploy overlays, the UI Bitbucket pipeline, and package metadata.
- Identified the four core findings (§4): nested `legacy/.github` is inert; legacy
  workflows stubbed; root workflow ignores legacy + ui; reusable skaffold actions are
  reusable as-is and legacy already has working skaffold/Dockerfile/overlays.
- Produced the phased plan (§5) and recorded open decisions (§6).
- No code/workflow changes made this session — research only.

### 2026-06-02 — Implementation session (snapshot + legacy build/deploy)
Split the work into two sides as requested: preserve the current CI/CD, and add the
legacy build/deploy pipeline.

**Side 1 — Saved the current monorepo CI/CD (snapshot):**
- `docs/ci-cd/current-monorepo-cicd/` — read-only copies of all 11 live root workflow
  files as of 2026-06-02, plus a `README.md` describing triggers, reusable actions,
  deploy targets, and known-state caveats. Nothing here executes (it's outside
  `.github/workflows/`); the live workflows are untouched.

**Side 2 — Implemented legacy build + deploy to all environments:**
- Parameterized the two reusable actions (backward-compatible; defaults preserve the
  API pipeline's exact behavior):
  - `_skaffold-build-k8s.yml`: added `working_directory` (default `.`) and
    `artifact_name` (default `build-artifact-json`); build runs in the working dir and
    uploads `<working_directory>/build.json` under the given artifact name.
  - `_skaffold-deploy-k8s.yml`: added matching `working_directory` + `artifact_name`;
    downloads the artifact into the working dir and runs `skaffold deploy` there.
- Added `legacy-pull_requests.yml` — on PRs touching `legacy/**`: build (dev test image
  repo) → deploy `jax-cluster-dev-10--dev`. Uses `working_directory: legacy`,
  `artifact_name: build-artifact-json-legacy`.
- Added `legacy-release.yml` — on push to main changing `legacy/pyproject.toml`:
  detect legacy version → build → deploy `--sqa` → (full release) `--stage` → `--prod`
  → draft GitHub release. Legacy is tagged independently as `legacy-v<version>` to avoid
  collision with the API's `v<version>` tags.
- Verified: legacy base `deployment.yaml` references `image: geneweaver-legacy`
  (matches the skaffold artifact name, so `--build-artifacts` substitutes correctly);
  legacy `skaffold.yaml` has all four GKE profiles; all four overlays exist. All four
  new/edited YAML files parse cleanly.

**Deliberately deferred (not in this session):**
- Legacy lint/test/coverage gates — legacy is Poetry/Py3.9 and code style "not yet made
  consistent" (per the original disabled `style.yml`); gating deploy on a failing ruff/
  pytest would block releases. Build+deploy (the explicit ask) ships first; gates are a
  fast-follow (Phase A4) once `legacy/tests` is confirmed green on Py3.9.
- Did not delete the dead nested `legacy/.github/` tree (Phase A1) — left for a separate
  cleanup commit to keep this change focused.
- Phase B (UI off Bitbucket, secrets/env setup, repo retirement) unchanged.

**Pre-merge requirement:** the four GKE GitHub Environments
(`jax-cluster-dev-10--dev/--sqa`, `jax-cluster-prod-10--stage/--prod`) and the GCP
secrets/vars (`GCLOUD_REGISTRY_SA_KEY`, `GCLOUD_CLUSTER_SA_KEY`, `CLUSTER_NAME/REGION/
PROJECT`) must exist on the `geneweaver` repo for the deploy jobs to run.

### 2026-06-02 — Implementation session (legacy lint/test gates + parallelization)
Added the deferred quality gates and parallelized the independent stages.

**Legacy lint/test gates (Poetry / Py3.9, not uv):**
- `_legacy-format-lint.yml` (new reusable) — Ruff `check` + `format --check` on
  `legacy/src` + `legacy/tests` (runs with `working-directory: legacy`).
- `_legacy-run-tests.yml` (new reusable) — installs the native system libs from
  `legacy/Dockerfile` (cairo, graphviz, imagemagick/wand, postgres client, boost),
  then `poetry install` + `poetry run pytest tests` in `legacy/`. Takes
  `python-version` + `runner-os` inputs; called via a matrix (`['3.9']` for now,
  trivially expandable).
- Wired as **blocking gates**: `build` now `needs: [format-lint, test]` (PR) and
  `needs: [version, format-lint, test]` (release).

**Parallelization (stages run concurrently where independent):**
- PR: `format-lint` ∥ `test` → `build` → `deploy(dev)`.
- Release: `version` ∥ `format-lint` ∥ `test` → `build` → `deploy_sqa` →
  `deploy_stage` → `deploy_prod` → `release`.
- The sqa → stage → prod **promotion chain stays sequential by design** (prod must
  not deploy before sqa/stage succeed) — that ordering is intentional, not a missed
  parallelization.

**Readiness caveat:** these are strict gates. Legacy style was previously flagged as
"not yet made consistent" and legacy tests may require services (DB, etc.) not present
on a bare runner. If the first runs are red, either land a legacy `ruff`/style cleanup +
test fixes, or temporarily relax (e.g. `ruff check --exit-zero`, or `continue-on-error`)
until legacy is green. CI wiring is correct independent of legacy code readiness.

**Legacy CI/CD file inventory (all in root `.github/workflows/`):**
`legacy-pull_requests.yml`, `legacy-release.yml`, `_legacy-format-lint.yml`,
`_legacy-run-tests.yml`, plus the shared (now parameterized) `_skaffold-build-k8s.yml`
and `_skaffold-deploy-k8s.yml`.

### 2026-06-02 — Legacy ruff/style cleanup (started)
Target standard: **the monorepo root `ruff.toml`** (`E,F,D,I,UP,B,C4,SIM,RUF` +
Google docstrings, line-length 99) — i.e. the same bar the migrated API follows inside
this repo. (The *standalone* `geneweaver-api` repo's `pyproject.toml` uses an older,
stricter selection incl. `ANN/C90/N/ERA/PD`; we matched the monorepo standard for
in-repo consistency. Switchable if desired.)

**Done this session:**
- Added `legacy/ruff.toml` mirroring the root standard, with `target-version = "py39"`
  (legacy's runtime — avoids UP rewriting to 3.10+ syntax) and excludes for vendored
  non-source trees (`src/static`, `src/tools/mset`, `sample-configs`).
- Deleted `src/tools/jaccardsimilarityblueprint2.py` — dead 2015 dev file containing an
  unresolved git merge-conflict marker (`<<<<<<< HEAD`), unreferenced, superseded by
  `jaccardsimilarityblueprint.py`.
- Confirmed `src/tools/mset/` is vendored C++/R research code (+ a Python-2 `demo/server2.py`),
  never imported → excluded from lint. The real `msetblueprint.py` lives outside it and is kept.
- Ran automated pass: `ruff check --fix` (safe only) + `ruff format`.
  **1678 → 1159 violations** (519 auto-fixed) and 40 files reformatted.
- Verified `python -m compileall` on all maintained legacy Python passes (only the
  excluded `mset/demo/server2.py` fails, as expected) → automated changes did not break parsing.

**Remaining (1159), by category:**
- **Docstrings ~750** — D103 (315 undocumented functions), D205 (212), D102 (100),
  D101 (77), D200 (33), etc. The bulk; tedious but low-risk.
- **Modernization/cleanup ~344 auto-fixable via `--unsafe-fixes`** — UP031 printf→format (98),
  C408 (34), many SIM. "Unsafe" = could change behavior; risky to bulk-apply on an
  untested codebase, so deferred pending review/smoke test.
- **Real bug-smells (manual) ~70** — F821 undefined-name (13, likely import-star fallout),
  F841 unused-variable (47), E722 bare-except (7), B904 (4), E711/E712/E721 comparisons (27),
  B006 mutable-default (2), B023 loop-var-closure (6).
- **E101 mixed-spaces-and-tabs (26)** — survive formatting (in strings/continuations); manual.

**Recommended next sequence:** (1) review + apply `--unsafe-fixes` then smoke-test the app;
(2) fix the bug-smell rules manually (F821/F841/E722/B904 — these are genuine quality issues);
(3) burn down the docstring backlog (largest, safest — good candidate for a focused pass).

**Gate note:** `_legacy-format-lint.yml` is currently a **blocking** gate, so until the
cleanup reaches zero, legacy PRs/releases will fail lint. Either keep it blocking to force
completion, or set `continue-on-error: true` temporarily while the burn-down proceeds.

### 2026-06-02 — Linting scoped per language (Python = ruff app-code only; UI = ESLint/Prettier)
**Python lint scoped to the application code only (not the whole legacy tree):**
- `legacy/ruff.toml` now `force-exclude = true` and excludes the non-Python projects
  (`src/static`, `src/tools/mset`, `sample-configs`, `migration`, `docs`, `deploy`).
- `_legacy-format-lint.yml` now lints by config scope (`ruff check .` / `ruff format --check .`)
  instead of hardcoded dirs, so it covers all legacy Python app code — `src/`, `src/tools/`
  (incl. `msetblueprint.py`, **not** the vendored `mset/` dir), `tests/`, and
  `curation-server/` — and nothing else.
- Re-ran the automated pass at the new scope (now includes `curation-server`, +102):
  **~1233 violations remaining**; all maintained Python still compiles.

**Legacy first-party UI JavaScript → same tooling as geneweaver-ui (ESLint + Prettier):**
- geneweaver-ui uses ESLint 9 flat config + `eslint-config-prettier` + Prettier 2.6
  (`.prettierrc: {singleQuote:true}`), via Nx (`nx lint`). Legacy has no Nx/Angular/TS, so the
  Nx/`angular-eslint`/`typescript-eslint` layers can't load — we keep the **same tools and
  versions** and the **same Prettier config**, on a plain-JS `@eslint/js` recommended base.
- Added in `legacy/`: `.prettierrc`, `.prettierignore`, `eslint.config.js`, `package.json`
  (devDeps pinned to geneweaver-ui's: `eslint ^9.8.0`, `eslint-config-prettier ^10.0.0`,
  `prettier ^2.6.2`, `@eslint/js ^9.8.0`; scripts `lint` / `lint:fix` / `format` / `format:check`).
- **Scope:** first-party GeneWeaver JS — `src/static/js/**` and `src/static/tools/**` — with
  vendored libs excluded (bootstrap, font-awesome, pixit, select2, d3 lib, `js/cytoscape/`,
  `js/d3.v3.js`, `**/*.min.js`). Templates (Jinja) and CSS deferred (Jinja breaks Prettier).
- Added gate `_legacy-ui-lint.yml` (Node 22 → `npm install` → `prettier --check` → `eslint`),
  wired as a parallel gate in both legacy workflows; `build` now also `needs: ui-lint`.

**Parallel gate layout now:** PR → `format-lint` ∥ `ui-lint` ∥ `test` → `build` → `deploy(dev)`;
Release → `version` ∥ `format-lint` ∥ `ui-lint` ∥ `test` → `build` → sqa → stage → prod → release.

**Pending burn-downs:** Python ruff (~1233) and the UI ESLint/Prettier violations (not yet
measured locally — needs `npm install`). Both gates are blocking; flip to `continue-on-error`
if deploys are needed before the burn-downs finish.

### 2026-06-02 — Reverted the automated formatting/fixes (user request)
- Restored all **44** legacy source files that the earlier `ruff format` + `ruff check --fix`
  pass had modified back to their original committed state (`git checkout HEAD -- legacy/`).
  No formatting/lint code changes remain applied; legacy source is pristine.
- This also **restored** `src/tools/jaccardsimilarityblueprint2.py` (the dead 2015 file with
  the unresolved `<<<<<<< HEAD` merge-conflict marker) that the earlier pass had deleted.
  → Resolved: the file is kept on disk but **excluded in `legacy/ruff.toml`**, so the Python
  lint gate skips it (verified: no longer reported).
- **Kept** the lint setup (not formatting): `legacy/ruff.toml`, `.prettierrc`, `.prettierignore`,
  `eslint.config.js`, `package.json`, and all the CI gate/workflow files. The standard and
  gates remain defined; only the bulk auto-edits to source were undone.
- Net: prior session-log entries describing the "1678 → 1233" reduction are **superseded** —
  those edits no longer exist in the tree. Counts there reflect what a future burn-down would
  start from, not current applied state.

### 2026-06-02 — Reconciliation against the original api workflows README
Compared this doc against `_original-README.md` (the geneweaver-api `.github/workflows/README.md`
copied into this folder) and found two items we had not captured:

**1. Deploys are gated on manual SQA approval (sqa, stage AND prod).**
The original README states every prod-registry deploy — **sqa, stage, and prod** — "waits for
approval from SQA before running this step." That approval is a **GitHub Environment
required-reviewer gate**, not something in the workflow YAML. Our reusable
`_skaffold-deploy-k8s.yml` already sets `environment: <name>`, so the legacy deploys
(`legacy-release.yml`: sqa → stage → prod) will inherit the same approval gates **provided the
four `jax-cluster-*` GitHub Environments are configured with required reviewers**. This means:
  - The pre-merge requirement is not just "the environments must exist" — they must also carry
    the **required-reviewer approval rules** (mirroring the api), or legacy promotions will run
    unattended instead of waiting for SQA sign-off.
  - Each legacy promotion to sqa/stage/prod is expected to **pause for SQA approval**, same as the api.

**2. Legacy is missing the coverage gate the api runs.**
The original README lists **coverage** in both the PR and release flows
(lint → tests → **coverage** → build → deploy). Our legacy workflows currently run
`format-lint` + `ui-lint` + `test` but **no `check-coverage`** job. This was deferred because
the shared `_check-coverage-action.yml` hardcodes `coverage-module: geneweaver.api` (wrong for
legacy) and legacy tests aren't confirmed green. To fully match the api template, a legacy
coverage gate is still **to-be-done**:
  - needs a legacy coverage module/target (not `geneweaver.api`),
  - depends on the legacy test suite passing on Py3.9 first (same prerequisite as the test gate).

*(Also noted, not added as action items: the live `.github/workflows/README.md` is stale —
it predates the monorepo's PyPI-publish / version-sync work and the legacy + ui pipelines — and
it has a typo referencing `_skaffold-deploy-action.yml` instead of `_skaffold-deploy-k8s.yml`.)*

### 2026-06-03 — Direction change: target the current platform (API + UI), drop legacy CI/CD
Once it was confirmed that `legacy/` is the **old monolithic Flask app** (not a consolidation
of the new repos) and that the live platform is the new **API** + **UI**, the CI/CD was
re-pointed accordingly.

**Removed (legacy-focused CI):**
- `.github/workflows/legacy-pull_requests.yml`, `legacy-release.yml`,
  `_legacy-format-lint.yml`, `_legacy-run-tests.yml`, `_legacy-ui-lint.yml`.
- (Recoverable from commit `478e8ed0`.) The legacy lint configs under `legacy/`
  (`ruff.toml`, `.prettierrc`, `.prettierignore`, `eslint.config.js`, `package.json`) are now
  orphaned — can be cleaned up separately.

**API — unchanged, already correct:** the root `pull_requests.yml` / `release.yml` build,
test, publish, and deploy `src/geneweaver/api` (+ `packages/*`). It is current/ahead of the
standalone `geneweaver-api` repo (which has been frozen since 2026-03-12, a state already
merged into the monorepo).

**UI — new GitHub Actions pipeline (translated from geneweaver-ui's Bitbucket pipeline):**
- `_ui-code-integrity.yml` — `npm ci` → seed `environment.ts` → `nx lint` → `nx test`.
- `_ui-deploy.yml` — per-env: download `ui-dist` artifact → upload static build to the GCS
  deployment bucket → `skaffold deploy -f ui/skaffold.yaml --profile <env>` (kustomize, no image build).
- `ui-pull_requests.yml` (paths `ui/**`): code-integrity → build dev+sqa (`npm run build:jax-cluster-dev-10`) → deploy **dev → sqa**.
- `ui-release.yml` (push main, paths `ui/**`): code-integrity → build all 4 (`build:jax-cluster-dev-10` + `build:jax-cluster-prod-10`) → deploy **sqa → stage → prod**.
- Same 4 GKE environments as the API; sqa/stage/prod stay sequential (SQA approval gates apply).

**Required repo secrets/vars for UI deploy:** `GCLOUD_CLUSTER_SA_KEY` (secret) and
`DEPLOYMENT_BUCKET`, `CLUSTER_NAME`, `CLUSTER_REGION`, `CLUSTER_PROJECT` (vars, per environment) —
the same set Bitbucket used (`$CLUSTER_SA`, `$DEPLOYMENT_BUCKET`, `$CLUSTER_*`).

**Still open:** the monorepo `ui/` is **stale** vs `geneweaver-ui` (missing the search-filters
feature, PR #20, ~2026-04-30) and has 3 uncommitted local edits — re-sync before retiring Bitbucket.

### 2026-06-29 → 07-01 — Legacy CI/CD re-introduced + tools-worker made to run in-container
Reverses the 2026-06-03 "drop legacy CI/CD" call: the legacy Flask app has to keep running in
the monorepo during (and after) the V3 switch, so its pipelines were added back and the
containerized tools-worker was fixed to actually work. Commits on the branch:

**CI/CD**
- `90e6bd5a` — root **API** Docker build was still running `poetry install` after the uv
  migration (and used `python:3.9`, but the code needs 3.10+ PEP-604 unions). Rewritten for uv
  on `python:3.12`; image builds, API imports (27 routes).
- `a9944276` — **`legacy-pull_requests.yml`**: on `legacy/**` PRs, build (dev/test registry) →
  deploy `jax-cluster-dev-10--dev`.
- `348c2cfd` — deploy the **tools-worker** alongside the legacy web (shares `geneweaver-pvc`).
- `acf50d85` — rename the PR pipelines by component (**API v3 / UI v3 / Legacy**) and add a
  `paths:` filter to the API pipeline (stop it running on pure `ui/**` / `legacy/**` PRs).
- `d76903b5` — **`legacy-release.yml`**: version bump on `legacy/pyproject.toml` →
  version-detect (Poetry `1.5.x`, `legacy-v*` tags) → build (**prod registry**, the
  `_skaffold-build` default) → deploy **SQA → Stage → Prod** → GitHub release draft. Pre-release
  versions stop at SQA; full versions promote through. Each deploy is env-gated by required
  reviewers. **This is the counterpart of the old standalone `geneweaver-legacy/release.yml`.**
- UI deploy: the missing per-env `DEPLOYMENT_BUCKET` variables were created on the repo (fixes
  the `gs://` provider-only-URL upload error) — repo config, not a commit.

**Legacy tools-worker (TOOLBOX C/C++ tools) — the real reason they never worked in a container**
- `14359acb` — the tools hardcoded `127.0.0.1/odeadmin` DB connections; made them env-driven
  (`db_conn.h` → `gw_conn_string()` from `DB_*`). **Pinned libpqxx 6.4.8** (built from source in
  the tools-worker Dockerfile) because the legacy code uses the ≤6 API (`connection_base`,
  `prepared()(...)`) that Debian's libpqxx 7 removed — so the binaries had silently never
  compiled. Also made `mset`/`CS_Mset` `createBackgrounds.py` env-driven.
- `e3e4ad03` — `genes.dat`/`homology.dat` were read from `/srv/...` but written to a nonexistent
  `/var/www/...`; made both env-driven (`gw_dist_data_dir()`, default `$APPLICATION_RESULTS/dist_data`
  on the results bucket) and fixed the malformed homology write.
- `f69400fb` — fixed a dangling-`c_str()` bug in the `distribution_generator` **prepopulation**
  path (stored `.c_str()` of a temporary → "invalid byte sequence for UTF8"); use the prepared
  statement, like the lookup path.
- Operational (not code): **backfilled `extsrc.jaccard_distribution_results` in dev** (set sizes
  ≤ 50, 1,275 pairs) so Jaccard significance works again.

**Security**
- `69d86897` — stopped logging the Auth0 `client_secret` in plaintext at CRITICAL on startup.
  ⚠️ The already-leaked value still needs **rotation** — tracked in
  `legacy/docs/TODO-auth0-secret-rotation.md` and Jira **G3-761**.

**Verification (`legacy/tools-worker/ab/`)**
- `5a7e44b3`, `1545471c` — a dev-vs-sqa tool **A/B harness**: dispatches the real Celery task in
  each env and diffs outputs, canonicalizing away env noise (run uuid, URLs, and the remapped
  internal `ode_gene_id`s). Result across all active tools: **equivalent**, the only substantive
  difference being JaccardSimilarity **p-values** — the *intended* effect of the dev distribution
  backfill (sqa returns `p=0`).

**How this changes the picture vs the old repos**
- The monorepo now **owns legacy dev** (via `legacy-pull_requests.yml`). sqa/stage/prod are still
  deployed by the **standalone `geneweaver-legacy` repo's** `release.yml` (image `59d15fb` on the
  prod registry). `legacy-release.yml` reproduces that promotion chain so the monorepo can take
  over — but the old repo's `release.yml` must be **frozen first** (both target the same clusters).
- The sqa/stage/prod namespaces are already provisioned (configmaps, `geneweaver-db`/`redis`/
  `geneweaver-legacy-secrets`, `geneweaver-pvc`, `gcp-secrets-manager` SecretStore all present),
  so the first promotion is mainly an image swap (old prod image → monorepo image) — validate in
  SQA first.

**Jira**
- Umbrella **G3-748** "Finish migration to the monorepo" now relates to the monorepo-migration
  tasks (G3-755/756/757/758 done; **G3-760** tools-worker fixes, **G3-761** Auth0 rotation,
  **G3-762** A/B harness).
- The **V3** replacement work (reimplementing tools on `packages/tools`) is a *separate* track
  under new epic **G3-763** "Switch from Geneweaver legacy to Geneweaver V3" (G3-749–753).

**Pre-merge / cutover checklist (unchanged + new)**
- Freeze the standalone `geneweaver-legacy` `release.yml` (manual-only) before enabling
  `legacy-release.yml`.
- Confirm the four GKE Environments carry required-reviewer approval rules (they do).
- Rotate the exposed Auth0 secret (G3-761).
