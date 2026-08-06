# Patterns: Legacy GeneWeaver → Monorepo Migration (tools-worker + CI/CD)

> Extracted: 2026-07-05
> Campaign: (ad-hoc session; no .planning/ campaign file — evidence = git history on branch G3-748-finish-migration-of-geneweaver-to-monorepo)
> Postmortem: none

## Successful Patterns

### 1. Env-driven config via a shared header (kill hardcoded infra assumptions)
- **Description:** Replaced hardcoded DB connection strings and file paths in legacy C++ tools with a shared `db_conn.h` (`gw_conn_string()` from `DB_*`, `gw_dist_data_dir()` from `APPLICATION_RESULTS`, `gw_mkdir_p()`), keeping the old values only as fallbacks.
- **Evidence:** commits `14359acb`, `e3e4ad03`.
- **Applies when:** containerizing/migrating legacy code that assumes localhost DBs or fixed filesystem paths.

### 2. Pin the exact legacy dependency instead of porting the code
- **Description:** Legacy C++ used the libpqxx ≤6 API (`connection_base`, `prepared()(...)`) that libpqxx 7 (Debian apt) removed. Rather than port the code, built **libpqxx 6.4.8 from source** into `/usr/local` (the TOOLBOX makefile already targeted `/usr/local`).
- **Evidence:** commit `14359acb`.
- **Applies when:** legacy native code fails to compile against a newer distro-provided library and porting is high-risk/low-value.

### 3. Validate a Docker recipe in an isolated build before touching the real Dockerfile
- **Description:** Built a throwaway `dgtest` image (`python:3.9` + libpqxx-from-source + the TOOLBOX sources) to prove the compile recipe, then baked the validated steps into `tools-worker/Dockerfile`.
- **Evidence:** session (pre-commit validation for `14359acb`/`e3e4ad03`).
- **Applies when:** a Dockerfile change is risky/slow to iterate through CI.

### 4. In-pod recompile to unblock an urgent data op, then commit for permanence
- **Description:** The prepopulation crash fix was compiled *inside the running pod* (which had the toolchain) to run the N=50 Jaccard backfill immediately, then committed so the image rebuild carries it.
- **Evidence:** commit `f69400fb` + the dev backfill (2,603 rows).
- **Applies when:** a data task is blocked by a code bug and the ~20-min CI/deploy cycle is too slow.

### 5. Local disk + one bulk copy instead of line-by-line writes to GCSFuse
- **Description:** Generating `genes.dat` (35M lines) directly onto the GCSFuse bucket took ~30 min (flush per line). Generating to `/tmp` (~3 min) then a single streaming `cp` to the bucket was ~10× faster.
- **Evidence:** session (genes.dat generation).
- **Applies when:** writing large files to a GCSFuse-mounted bucket.

### 6. A/B parity harness that diffs computed metrics, not raw IDs
- **Description:** To verify dev vs sqa tool parity, dispatched the real Celery task in each env and diffed outputs after canonicalizing away known-divergent fields (run uuid, URLs, and the remapped internal `ode_gene_id`s — compared by count/symbol). Bags (gene-id-keyed dicts) compared as multisets.
- **Evidence:** commits `5a7e44b3`, `1545471c`.
- **Applies when:** verifying behavioral equivalence across environments whose data has drifted (surrogate-key remaps, symbol renames).

### 7. Mirror the existing promotion chain when migrating CI
- **Description:** The monorepo `legacy-release.yml` reproduces the old standalone repo's chain (version-gated build → SQA → Stage → Prod → release draft), adapted with `working_directory: legacy`, the prod registry default, and namespaced `legacy-v*` tags.
- **Evidence:** commit `d76903b5`.
- **Applies when:** moving a deploy pipeline into a monorepo — preserve semantics, adapt scoping.

### 8. Read the *real* cause under a truncated CI error
- **Description:** A generic "Docker build failed / please retry" masked the actual line `[tool.poetry] section not found` — the root Dockerfile still ran `poetry install` after the project migrated to uv. Pulling full CI logs revealed it.
- **Evidence:** commit `90e6bd5a`.
- **Applies when:** CI wrappers hide the underlying tool error — fetch the full log.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Pin libpqxx 6.4.8 from source vs port to 7.x | Lower risk for legacy C++; makefile already targets /usr/local | ✅ compiled + deployed |
| `genes.dat`/`homology.dat` on PVC via `APPLICATION_RESULTS`, generate to /tmp then copy | Persist across pods; avoid GCSFuse per-line slowness | ✅ files on bucket, backfill worked |
| Backfill via in-pod recompiled binary, commit for image | Unblock the data task now; permanence via CI later | ✅ 1,275 pairs / 2,603 rows |
| A/B compare on metrics, ignore raw gene IDs | dev remapped `ode_gene_id`; raw diff is all false-positives | ✅ surfaced only the real p-value diff |
| Namespaced `legacy-v*` release tags in monorepo | Avoid collision with API/UI release tags | Sound (pending first release) |
| Freeze old repo before enabling monorepo release | Both target the same sqa/stage/prod clusters | Pending (owner-managed) |
| Deploy the monorepo API on `python:3.12` (not 3.9) | Code uses PEP 604 unions; dev/prod run 3.12 | ✅ app imports, 27 routes |
