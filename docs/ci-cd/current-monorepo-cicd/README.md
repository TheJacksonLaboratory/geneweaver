# Monorepo CI/CD — Point-in-Time Snapshot

This folder is a **read-only snapshot** of the GeneWeaver monorepo's GitHub Actions
CI/CD as it existed on **2026-06-02**, captured before the legacy build/deploy
pipeline was added. These files are copies for reference and history — the
**live, executing** workflows are in `/.github/workflows/`.

> ⚠️ Nothing in this folder runs. GitHub Actions only executes workflows located in
> the repository-root `.github/workflows/`.

## What the snapshot covers

At capture time the monorepo CI/CD covered the **API + Python workspace packages only**
(`src/geneweaver/api` + `packages/{core,db,client}`). It did **not** build or deploy
`legacy/` or `ui/`.

### Triggers
| File | Trigger | Purpose |
|---|---|---|
| `pull_requests.yml` | PR → `main`/`master` | lint → coverage → test → version-sync → build → deploy **dev** |
| `release.yml` | push to `main`/`master` when root `pyproject.toml` changes | lint → coverage → test → version detect/sync → `uv build` + PyPI publish (root + all packages) → deploy **sqa → stage → prod** |
| `style.yml` | push → `main` | standalone ruff lint |
| `tests.yml` | push → `main` | standalone test matrix (py3.9/3.10/3.11) |
| `coverage.yml` | push → `main` | standalone coverage |

### Reusable (`workflow_call`) building blocks
| File | Tooling | Notes |
|---|---|---|
| `_format-lint-action.yml` | **uv** | `ruff check` + `ruff format --check` on `src/ tests/` |
| `_run-tests-action.yml` | **uv** | `uv sync --all-packages`, runs root `tests/` + each `packages/*/tests/` |
| `_check-coverage-action.yml` | **Poetry** ⚠️ | still poetry-based; `coverage-module` hardcoded `geneweaver.api`; pushes coverage + radon complexity to Atlassian Compass |
| `_skaffold-build-k8s.yml` | skaffold | build image → upload `build.json` |
| `_skaffold-deploy-k8s.yml` | skaffold | download `build.json` → deploy to GKE profile |

### Deploy targets (GKE, via skaffold kustomize profiles)
`jax-cluster-dev-10--dev`, `jax-cluster-dev-10--sqa`,
`jax-cluster-prod-10--stage`, `jax-cluster-prod-10--prod`

## Known state at snapshot time (see `LEGACY_CICD_MIGRATION.md`)
- Legacy and UI not wired into any pipeline.
- uv/Poetry split: lint+test migrated to `uv`, coverage step still Poetry.
- `style.yml` / `tests.yml` / `coverage.yml` fire on every push to main, overlapping with `release.yml`.
