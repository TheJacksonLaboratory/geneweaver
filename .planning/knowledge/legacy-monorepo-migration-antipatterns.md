# Anti-patterns: Legacy GeneWeaver → Monorepo Migration

> Extracted: 2026-07-05
> Campaign: (ad-hoc session; evidence = git history on branch G3-748-finish-migration-of-geneweaver-to-monorepo)

## Failed Patterns

### 1. Hardcoded DB connection / file paths in tools
- **What was done:** TOOLBOX C++ tools hardcoded `dbname=geneweaver user=odeadmin hostaddr=127.0.0.1 port=5432`, read `genes.dat` from `/srv/geneweaver/...`, and `fileGenerator` wrote it to a *different* nonexistent `/var/www/html/...`. Python `createBackgrounds.py` hardcoded `odeadmin@crick.ecs.baylor.edu`.
- **Failure mode:** In the containerized worker the DB is remote and those paths don't exist → tools couldn't connect and `distribution_generator` failed with "genes.dat failed to open"; `jaccard_distribution_results` stayed empty (no Jaccard significance).
- **Evidence:** TOOLBOX audit; commits `14359acb`, `e3e4ad03`.
- **How to avoid:** Read all infra (DB, paths, brokers) from env vars with sane fallbacks; keep read/write paths consistent.

### 2. Dangling `c_str()` on a temporary std::string
- **What was done:** `sqlTwo = CreateInsertQuery(...).c_str(); N.exec(sqlTwo);` — stored a pointer into a temporary freed at the `;`.
- **Failure mode:** `N.exec` read freed memory → Postgres "invalid byte sequence for encoding UTF8"; prepopulation crashed on the first row (so it never worked, despite the lookup path working via a prepared statement).
- **Evidence:** commit `f69400fb`.
- **How to avoid:** Pass the `std::string` directly to `exec`, or use a prepared statement (`executeInsertResult`). Never assign `.c_str()` of a temporary to a variable.

### 3. Swallowing build/compile failures with `|| echo WARN`
- **What was done:** The tools-worker Dockerfile compiled each TOOLBOX dir with `... || echo "WARN: make failed in $d"`.
- **Failure mode:** `distribution_generator.o` never compiled (libpqxx mismatch) but the image build "succeeded"; the missing binary only surfaced at runtime as a silent no-op.
- **Evidence:** session diagnosis (binary absent in image; build green).
- **How to avoid:** Let critical build steps fail the image, or explicitly assert artifacts exist after the loop.

### 4. Logging secrets
- **What was done:** `logging.critical('Auth0 client_secret: ' + config.get('auth','client_secret'))` on every startup.
- **Failure mode:** The Auth0 client_secret was written to pod stdout / Cloud Logging in plaintext → credential exposure (still requires rotation).
- **Evidence:** commit `69d86897`; tracked in G3-761.
- **How to avoid:** Never log secrets; log only non-secret config (client_id, domain, endpoints).

### 5. Stale Dockerfile after a build-system migration
- **What was done:** Root project migrated Poetry → uv, but the root `Dockerfile` still ran `poetry install` (and used `python:3.9`, comma-broken `ENV`).
- **Failure mode:** CI build failed (`[tool.poetry] section not found`); masked by a generic retry message.
- **Evidence:** commit `90e6bd5a`.
- **How to avoid:** When changing build systems, grep for and update all Dockerfiles/CI that invoke the old tool.

### 6. Line-by-line writes to a GCSFuse mount
- **What was done:** Generated a 35M-line file straight onto the GCSFuse bucket (flush per line).
- **Failure mode:** ~30 min and counting; effectively a performance failure.
- **Evidence:** session.
- **How to avoid:** Write large files to local disk, then one bulk `cp` to the bucket.

### 7. Relying on `paths:` filters within a mega migration PR
- **What was done:** Assumed the `legacy/**` / `ui/**` path filters would scope which pipelines run.
- **Failure mode:** For `pull_request` events the filter is evaluated against the *whole PR diff*; the migration PR touched everything, so all pipelines fired every push.
- **Evidence:** commit `acf50d85` (added a path filter to the API pipeline; noted filters only help scoped PRs post-merge).
- **How to avoid:** Expect broad PRs to trigger everything; scope with path filters knowing they take effect for future narrow PRs.

## Operational gotcha (not a code anti-pattern)
- **sqa Celery worker wedged after a redis blip** — connected but not consuming (tasks piled up in the queue, `inspect` no-reply). Recover with `kubectl rollout restart deploy/geneweaver-legacy-tools -n sqa`.
