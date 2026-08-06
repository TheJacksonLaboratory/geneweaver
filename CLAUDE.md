# CLAUDE.md

Complements `AGENTS.md` (repo overview, setup, validation). This file holds
durable engineering guardrails learned from real incidents. Full context in
`.planning/knowledge/`.

## Engineering guardrails

### Secrets
- **Never log secrets.** No `client_secret`, password, token, or API key in log
  statements — they leak to pod stdout / Cloud Logging. Log only non-secret
  fields (client_id, domain, endpoints). (Auth0 client_secret was logged at
  CRITICAL on every startup — see G3-761.)

### Configuration
- **Read all infrastructure from the environment, never hardcode it.** DB
  connection (`DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USERNAME`/`DB_PASSWORD`), broker
  URLs, and file paths must come from env vars (with sane fallbacks) — not
  literals like `127.0.0.1`, `odeadmin`, `/srv/...`, or `/var/www/...`. Hardcoded
  infra breaks the moment code runs in a container / different environment.
- Keep a file's **write path and read path consistent** (one env-derived
  location), and create the directory before writing.

### Database
- **Parameterise SQL — never `%`-interpolate a query string.** Use
  `cursor.execute(sql, (a, b))`, not `cursor.execute(sql % (a, b))`. Route values
  reach these unvalidated: `gsid` arrives as `request.args['gs_id']` in
  `/updateGenesetGenes` and was interpolated straight into an `UPDATE`. ~42
  occurrences remain in `legacy/src` (`geneweaverdb.py`, `genesetblueprint.py`,
  `uploadfiles.py`) — fix the line you are touching rather than adding another.
- **Derive a denormalized count or cache from the rows it describes, not from a
  parallel count of something else.** Where the write path aggregates (`GROUP BY`,
  `DISTINCT`, a filter), a separately computed count is a *different number* by
  construction. `gs_count` was set from the staged rows in `temp_geneset_value`
  while the INSERT stored one row per distinct `ode_gene_id`, so two identifiers
  for the same gene inflated it — search (which reads `gs_count`) and the geneset
  page (which counts live) then disagreed. Compute it *after* the rows exist:
  `SET gs_count = (SELECT count(*) FROM extsrc.geneset_value WHERE gs_id = …)`.
  (GWC-34 / G3-782.)

### Build / CI
- **Do not swallow build or compile failures.** Avoid `... || echo "WARN: ..."`
  around critical steps — it produces a green build with a missing artifact that
  only fails silently at runtime (e.g. `distribution_generator.o` never built).
  Let the step fail, or assert the artifact exists afterward.
- **When changing a build system, update every Dockerfile and CI workflow that
  invokes the old tool.** (Root project moved Poetry → uv but a Dockerfile still
  ran `poetry install`; the setup notes in `AGENTS.md` still say `poetry` too —
  update them when touching that area.)
- **Read the real error under CI wrappers.** A generic "build failed / retry"
  often hides the actual cause (e.g. `[tool.poetry] section not found`) — pull
  the full log.

### Legacy native tools (`legacy/tools-worker`)
- **Pin the legacy dependency version rather than porting** when native C++ fails
  against a newer distro library (e.g. libpqxx 6.4.8 from source, since the code
  uses the ≤6 API that libpqxx 7 removed).
- In C++, **never assign `.c_str()` of a temporary to a variable** — the
  temporary is freed at the `;`, leaving a dangling pointer (caused
  "invalid byte sequence for encoding UTF8"). Pass the `std::string` to `exec`
  or use a prepared statement.

### Large files on GCSFuse buckets
- **Generate large files on local disk, then one bulk `cp` to the bucket.**
  Line-by-line writes to a GCSFuse mount flush per line and are ~10× slower
  (a 35M-line file: ~30 min direct vs ~3 min via /tmp + copy).

### Deploy / environments
- dev and sqa share the Cloud SQL instance `jax-dev-10-guided-jay`; stage and
  prod share `jax-prod-10-promoted-owl`. Internal `ode_gene_id`s were remapped in
  dev's Dec-2025 reload, so genesets are the same biology with different internal
  IDs — compare tool outputs on metrics, not raw IDs (see `legacy/tools-worker/ab/`).
- The monorepo currently owns **dev** for legacy; sqa/stage/prod are still
  deployed by the standalone repos. Freeze the old repo's release pipeline before
  enabling the monorepo `legacy-release.yml` to avoid double-deploys.
