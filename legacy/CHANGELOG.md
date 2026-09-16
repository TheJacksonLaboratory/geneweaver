# GeneWeaver Legacy — Changelog

Changes to the legacy GeneWeaver application (`legacy/`), released from the monorepo via
`.github/workflows/legacy-release.yml` and tagged **`v<version>`** (e.g. `v1.6.0a`).

**Pushing the tag is the release decision** — merging a version bump to `main` deliberately does
*not* release (`cb61c111`; a merged branch carrying a bump once fired an unintended prod-bound run).
The tag must match `legacy/pyproject.toml` or the run fails. A version containing a letter is a
pre-release and deploys to **SQA only**; a plain version promotes through Stage and Prod.

⚠️ **The letter is a PEP 440 pre-release segment, not a free-form counter, and it runs out at `c`.**
Python normalises `a`→alpha, `b`→beta and `c`→**`rc`**, so the installed version does not always
read back the way it was written:

| written | installed / footer |
| --- | --- |
| `1.6.0a` | `1.6.0a0` |
| `1.6.0b` | `1.6.0b0` |
| `1.6.0c` | **`1.6.0rc0`** — `c` is the canonical abbreviation for `rc` |
| `1.6.0d` | **invalid** — `InvalidVersion`; there is no `d` segment |

So `1.6.0c` is the last pre-release available in this scheme. A fourth needs an explicit release
candidate (`1.6.0rc1`, `1.6.0rc2`, …), which normalises to itself. Verified in the release image.

---

## 1.6.2 — unreleased

The `/findPublications` fix (G3-825). **No database migration**, and no gene set's
membership changes — the route only reads.

### Fixed — `/findPublications` (G3-825)

`get_similar_genesets_by_publication` shipped in **2015** (`ffd24d80`, "Created a view other
genesets with the same publication id page. Still needs some jquery work…") with four defects
and kept all four for eleven years. The only changes since were a rename
(`geneset_is_readable` → `geneset_is_readable2`, `0ce99c4d`, 2017) and a whole-file
tabs-to-spaces reindent (`e966e3c5`, 2016) — which shows up in a `git log -S gs_ids_clean`
search and looks like a semantic change to this function, but is not. The function in the
image Prod ran before 1.6.0 (`59d15fb-dirty`) is byte-identical to the one 1.6.1 shipped.

* **One permission round trip per sibling gene set, and the answers were discarded.**
  `geneset_is_readable2` was called in a Python loop, one `cursor.execute` each, into
  `gs_ids_clean` — which was then never read, because the final query used the unfiltered
  `gs_ids`. Measured on Prod for `gs_id 374128` (PMID 10802651, the GO Consortium paper,
  **14,799** gene sets): **18.62 s**, 1.26 ms a call. The same predicate inside the query
  costs **~13 µs a row** — same number of evaluations, no round trips. The predicate is now
  part of the statement, so it cannot be computed and ignored.
* **A gene set with no publication returned HTTP 500.** The id list was interpolated into
  `IN (%s)`, so an empty list produced `IN ()` → `psycopg2.errors.SyntaxError`. **154,651** of
  Prod's gene sets (56%) have no `pub_id`. Caught in Prod's own log on **2026-09-13**, two days
  before 1.6.0 deployed, so this predates the 1.6 line entirely. Now
  `g.pub_id = (SELECT pub_id FROM geneset WHERE gs_id = %(gs_id)s)`: a NULL publication makes
  the comparison NULL, which matches nothing and returns zero rows. `gs_id` is the primary key,
  so the scalar subquery can never return more than one row.
* **The discarded filter showed logged-in callers gene sets they could not read.** Whatever
  `geneset_is_readable2` said about a sibling, every sibling was rendered:
  `viewsamepublications.html` prints `name`, `abbreviation`, `description`, `count`, `cur_id`,
  `sp_id` and `attribution` per row. Demonstrated on Prod: for a real non-admin account and a
  gene set that account may not read, the old query returned **3 rows** and the fixed one
  returns **0**. Gene *values* are not exposed by that template.

  **Scope correction.** The first version of this entry, of G3-825 and of PR #24 said an
  *anonymous* visitor was shown that metadata. That is wrong, and the review caught it:
  `viewsamepublications.html` opens with `{% if user_id == 0 %}` and includes
  `permissionError.html`, so an anonymous caller never reaches the rows at all. The **170**
  publications that mix readable and non-readable gene sets and the **14,630** gene sets with a
  publication that are not publicly readable are still real, but they measure the *restricted
  population*, not what an anonymous visitor could see. The exposure is to authenticated users;
  the route's lack of `@login_required` mattered only in that it let an anonymous request run
  ~32 s of queries to be told it had no permission.
* **`%`-interpolation of a query string**, against the `CLAUDE.md` database guardrail. The
  values were database-derived integers, so it was not injectable; it is the prohibited pattern,
  and it is what made the `IN ()` crash possible.

### Fixed — a caller could probe a gene set they cannot read

Raised in review. The scalar subquery resolved the viewed gene set's `pub_id` without checking
that the caller may read *it* -- only the siblings were filtered. So a logged-in caller could
ask for a restricted `gs_id` and the readable siblings that came back disclosed which
publication it is attached to. The subquery now carries the same check, so an unreadable gene
set resolves to NULL and the page shows its empty state. It also makes
`count_similar_genesets_by_publication`'s documented "counts the viewed gene set itself" true,
which it was not when the viewed set was filtered out of nothing.

The route additionally returns before either query when `user_id == 0`, since the template
renders `permissionError.html` for that case and never reaches the rows.

### Fixed — the second N+1, which is why the page is capped

Better SQL alone would not have fixed the timeout. Each row becomes a `Geneset`, and
**`Geneset.__init__` calls `get_all_publications()`** for any set with a publication — its own
query on its own pooled connection, **0.91 ms** measured on Prod, so **~13.5 s** for that
publication before Jinja renders a block each. The observed failure was 61.08 s against 19.01 s
of membership queries; this is most of the remainder.

So the route now renders **one bounded page**: `SIMILAR_BY_PUBLICATION_PAGE_SIZE = 100`, with
`LIMIT`/`OFFSET`, `ORDER BY g.gs_id`, and a `count_similar_genesets_by_publication` total behind
Previous/Next links. The template's empty state now keys off that **total** rather than the
length of the page — with paging, a last page can legitimately hold one row while the
publication has thousands, and `length < 2` would have read that as "no other GeneSets". The
total counts the viewed gene set itself, so `< 2` still means "no others", unchanged.

The page-size constant carries the reason in a comment: the cap is what bounds the route, and
raising it re-introduces the per-object publication lookups linearly.

### Measured, against `geneweaver-prod`

Read-only, 2026-09-16, with the exact SQL the new code generates:

| case | count query | page query | rows | total |
|---|---|---|---|---|
| `gs_id 374128` — 14,799 siblings | 0.207 s | 0.200 s | 100 | **0.407 s** |
| `gs_id 408661` — no publication | 0.001 s | 0.001 s | 0 | **0.002 s** |
| `gs_id 999999999` — no such gene set | 0.001 s | 0.001 s | 0 | 0.002 s |

Plus **0.078 s** for the 100 `Geneset.__init__` publication lookups one page now triggers.
About **0.49 s** in total, against 19 s + 13.5 s before, and the 61.08 s the live request took
before it was killed. The count returns **14,797**, not 14,799 — two of that publication's gene
sets fail the readability check, which is the filter now doing its job.

Deep paging does not degrade: `OFFSET 14750` measured 0.240 s against 0.197 s at `OFFSET 0`,
because the sort materialises the matching rows for any page. Two caveats worth keeping: those
are warm-cache numbers (72,691 buffer accesses, all hits), and the cost is linear in publication
size rather than bounded — 0.2 s at 14,799 rows against a 60 s worker ceiling is a wide margin,
not a guarantee.

### Not fixed here

Whether this route should require a login outright, rather than running and then rendering a
permission error, is left as its own decision on G3-825. The queries no longer run for an
anonymous caller, so the cost of that is now zero.

### Testing & developer tooling

* `legacy/tests/db/test_find_publications.py` — **22 tests**, wired into the explicit module
  list in `_legacy-tests.yml`; suite **194 → 216**. Three groups: the two queries (one statement
  per page, the predicate in the SQL, equality not `IN`, no interpolation, `mogrify` never
  called, every value bound, anonymous → `-1`, `LIMIT`/`OFFSET`/`ORDER BY` present, the page size
  bounded); the route on its parsed AST, as `tests/test_search_filters.py` does, because
  `src/application.py` builds the Flask app at import and cannot be imported in a unit test; and
  the template contract, so the empty state cannot drift back to testing the page length.

### Version

* No version bump in this branch. `legacy/pyproject.toml` stays at **1.6.1**; the bump to
  **1.6.2** belongs in its own release PR, as 1.6.0 and 1.6.1 did, because the tag is the release
  decision and a merged bump must not be able to fire a prod-bound run on its own (`cb61c111`).

---

## 1.6.1 — released 2026-09-16

> Tagged `v1.6.1` on `71b66e24` and promoted SQA → Stage → Prod the same day. **This is
> the build Prod runs.** Verified on the deployed pods: image `71b66e2@sha256:d0a305fb…`,
> `poetry version` 1.6.1, the served footer reading *Application Version 1.6.1*, 1 master
> + 4 workers at `--timeout 60`, `/healthz` 204, and the HPA reading a real CPU value
> rather than `<unknown>`.

**The promotion release for the outage fix.** Not new application behaviour: 1.6.1 carries the
*same application code* as `1.6.1a`, which SQA verifies first. What changes is the release *shape* —
a plain version with no letter, so the workflow promotes **SQA → Stage → Prod** and drafts a GitHub
release, instead of stopping at SQA.

> **Every deploy is still gated.** Pushing the tag queues the Stage and Prod deploy jobs behind their
> GitHub environment approvals; it does not deploy anything on its own. **Do not approve Prod until
> SQA has signed off 1.6.1a** — that pass is what this release rests on.

> ⚠️ **Prod is two releases behind.** It has been serving the pre-1.6.0 image (`59d15fb-dirty`) since
> the 2026-09-16 rollback, so approving Prod here delivers **1.6.0's application changes and 1.6.1's
> limits at once**. The Prod verification pass has to cover 1.6.0's scope — thresholds, search,
> curation, the tool routes — not just the concurrency fix. Stage and SQA are on 1.6.0 already and
> move one step.

### Changed since 1.6.1a

Nothing but this version bump and the changelog. `git diff v1.6.1a..main` touches two files, neither
under `legacy/src`.

### Why the version jumps to 1.6.1 rather than reusing 1.6.0

`v1.6.0` is already tagged (`5e3892c`) and released, and it points at code *without* the outage fix —
283 changed lines across `legacy/src`, the Dockerfile and the deploy overlays separate the two. Tag
and `legacy/pyproject.toml` have to agree, and a released version has to keep describing its own
artifact, so the fix ships as the next patch version.

### Required before each environment

**Database: nothing to do.** Migrations 117, 118 and 119 are applied and verified in every
environment, Prod included — this release adds none.

| | 117 | 118 | 119 |
|---|---|---|---|
| Dev | applied | applied | applied |
| SQA | applied | applied | applied |
| Stage | applied 2026-09-15 | applied 2026-09-15 | applied 2026-09-15 |
| Prod | applied 2026-09-15 | applied 2026-09-15 | applied 2026-09-15 |

Two deploy-time notes specific to this release:

* **The Prod apply adopts the HorizontalPodAutoscaler.** The live `geneweaver-legacy` HPA was created
  imperatively and carries no `last-applied-configuration` annotation, so the first apply of the
  now-in-Git manifest emits a warning and patches the annotation in. Expected, and it is the point:
  the HPA's bounds and its web-container CPU metric stop living only in the cluster. Its
  `spec.replicas` stays HPA-owned — the overlay removes the field outright.
* **The web container's CPU and memory requests move into Git** at the values Prod runs today
  (`cpu: 1`, `memory: 1092Mi`). Nothing about scheduling changes; what changes is that the HPA's
  `Utilization` target no longer depends on values inherited from the standalone repo's pipeline
  through `kubectl apply`'s three-way merge.

The JaccardSimilarity `.dat` caches are already generated in every environment and live on the
results PVC, so they survive pod replacement and this deploy. No regeneration step this time.

### What to watch after the Prod deploy

* **`WORKER TIMEOUT` should stay at zero.** It was 35 in two hours during the incident and zero in
  the 14 days before it, so it is a clean signal. `--timeout` is now 60 s, so a stuck worker is
  replaced inside a minute rather than five.
* **The HPA should visibly respond to load.** With four workers per pod, a busy pod burns CPU, which
  is what the autoscaler measures; during the incident a single blocked worker burned none and Prod
  sat at its floor of 2 through a total outage.
* **The scraper may return.** The application changes raise the ceiling — request concurrency at the
  Prod floor goes from 2 to 8 — but the two edge mitigations are still open: `proxy-next-upstream`
  off for timeouts, and rate-limiting.

### Known issues carried forward

* ⚠️ **A stale duplicate `public.process_thresholds` exists on Prod and SQA** (not Dev, not Stage),
  carrying the pre-117 body — Binary as `value > threshold`, P/Q inclusive, type 4/5 on
  `ABS(value)`. It predates migrations 117/118/119, which correctly replaced
  `production.process_thresholds`. The application is unaffected (the pool sets `search_path TO
  production, extsrc, odestatic`, which excludes `public`), but any session resolving `public` first
  calls the unfixed function. Needs its own migration; not addressed by this release.
* **Stage only:** 6,200 of 6,386 type-1/2 rows sitting exactly on their cutoff are flagged
  in-threshold against an exclusive procedure. SQA (0 of 28,205) and Prod (0 of 14,610) are clean.
  A G3-819 follow-up.
* **Prod only:** 2,956 gene sets claim genes while holding none. Migration 118 deliberately leaves
  them alone. Its own ticket.
* A `NaN` threshold puts every gene in threshold (`1 < 'NaN'::numeric` is TRUE in PostgreSQL).
  Unchanged; 0 live gene sets carry one on SQA.

### Version

* `legacy/pyproject.toml` 1.6.1a → **1.6.1**. A full release — no letter — so the workflow promotes
  through **Stage and Prod** and drafts a GitHub release. Release with
  `git tag v1.6.1 && git push origin v1.6.1` on the commit carrying this bump; the bump alone does
  not release, and the version job fails the run if tag and file disagree.
* Installs as **`1.6.1`** with no normalisation, unlike the lettered pre-release (`1.6.1a` →
  `1.6.1a0`). PEP 440 orders `1.6.1a0 < 1.6.1`, so this is an upgrade from what SQA runs once
  1.6.1a is deployed.
* ⚠️ **Artifact identity:** this builds a *new* image. SQA's 1.6.1a sign-off does not transfer to it,
  so §4.3.2's TOOLBOX binary assertion needs re-running against this build. Identity does hold
  *within* the run — one image is built and that same artifact is deployed to SQA, Stage and Prod in
  turn, with SQA re-verified as the first hop.

---

## 1.6.1a — tagged 2026-09-16; SQA deploy awaiting approval

> `v1.6.1a` is pushed and the image is built; the SQA deploy job is queued behind its GitHub
> environment approval. Nothing is deployed until someone approves it.

**The outage-response pre-release.** No application behaviour changes and no migration: 1.6.1a is
1.6.0 plus the limits and health gates that stop one blocked request from taking the site down. A
**pre-release, SQA only** — Prod goes back to a plain version once this is verified.

> **Why a patch bump and not `1.6.0d`.** The letter is a PEP 440 pre-release segment and there is no
> `d`; `1.6.0c` was already the last one available, and `1.6.0` itself is released. So the next
> pre-release has to hang off the next patch version: `1.6.1a`, installed as **`1.6.1a0`**.

### The outage this responds to

Reconstructed from the ingress access log and the container logs after the rollback. All times UTC,
2026-09-15/16.

| | |
|---|---|
| 19:38 | 1.6.0 deployed to Prod. Serves for **4 h 07 m at a 0.06 s mean** request time. |
| 23:45 | A scraper starts walking gene identifiers through `/search/`, **47 → 422 requests per minute**, rotating desktop user agents. Prod runs 2 pods × **1 Gunicorn worker** — two requests at a time — so arrivals run several times over capacity. Before this, Prod took 1–4 searches per five minutes. |
| 23:45+ | Requests cross ingress's 5 s upstream timeout and ingress **retries the next upstream**, so one client request becomes three (`5.001, 5.000, 0.625` / `504, 504, -`). The client gives up (499) while Gunicorn keeps writing the response to a socket nobody reads: every worker died inside **`sock.sendall()`** at the 300 s timeout. **35 `WORKER TIMEOUT`s in two hours, against zero in the preceding 14 days.** |
| 01:48 | Rollback. The fresh pods serve fast enough to raise CPU, the HPA scales **2 → 7**, and the same scraper is absorbed. |
| 02:05 | The HPA scales back to 2 pods and the **rolled-back** image starts degrading under the same scraper too: 6 s mean, 266 client aborts per five minutes. |

Two conclusions shape this release:

* **Nothing in 1.6.0 was slower.** The code this scraper's URL executes is unchanged — the deployed
  1.6.0-predecessor `/app/src` was pulled out of the running Prod pod and diffed against the
  release: `render_searchFromHome`, `get_geneset_no_user` and the search templates are identical,
  and the `search.py` changes are guards that do not fire on this URL shape. The database, Sphinx
  and GCSFuse were healthy throughout, and no autovacuum ran on `geneset`/`geneset_value` in the
  window.
* **A blocked write burns no CPU**, so the CPU-driven HPA held Prod at its floor of 2 for the whole
  outage — the autoscaler could not see a total outage. More workers per pod is what makes CPU a
  meaningful signal again.

### Fixed — request concurrency and unbounded waits (#20)

* **Four Gunicorn workers per pod, every environment.** Gunicorn's `workers` default is
  `int(os.environ.get("WEB_CONCURRENCY", 1))` and the Dockerfile `CMD` passes no `--workers`, so
  every pod in every environment has been running **one** worker and had no concurrency at all.
  `WEB_CONCURRENCY=4` is set in the base. Four fits the web container's measured memory budget —
  one live worker at 177–190 MiB against a ~1.1 GiB request. At the Prod floor, request concurrency
  rises from **2 to 8**.
* **Gunicorn `--timeout` 300 → 60 s.** A worker writing to an abandoned socket was held for five
  minutes; it is now replaced within one.
* **`/healthz` plus startup, readiness and liveness probes** on the web container. A saturated pod
  is taken out of service instead of absorbing requests it cannot answer, and a container that does
  not recover is restarted. The endpoint is deliberately trivial (`204`, no database) so it reports
  worker availability rather than dependency health.
* **Readiness gated on Sphinx.** The search sidecar gets TCP probes, with a startup budget covering
  the measured four-minute cold index build, so a pod cannot serve searches against a searchd that
  is not listening yet.
* **Sphinx socket operations bounded at 2 s** (`SPHINX_TIMEOUT_SECONDS`); the locked
  `sphinxapi-py3` 2.1.11 `SetConnectTimeout(float)` applies the socket timeout before connect and
  retains it for response reads, so this bounds reads as well as connects.
* **NCBI calls bounded.** PubMed at 10 s (`PUBMED_TIMEOUT_SECONDS`), SRA at `(3.05, 10)`
  connect/read (`NCBI_TIMEOUT`). The optional SRA lookup now **fails open** — on a timeout, a
  malformed response, or an HTTP error such as the 429s observed in Prod logs — and logs a warning
  instead of failing the gene set page. Found while reading the incident logs, not part of the
  collapse.
* **Connection pool 5–20 → 1–5 per worker.** With synchronous workers, five idle connections per
  worker turned a worker-count increase into dozens of idle sessions per pod. Prod peaked at 15 of
  600 connections during the incident, so this is headroom management rather than a fix.

### Infrastructure & operations

* **The Prod web HPA is now declared in Git** (min 2 / max 8), scaled on the **web container's** CPU
  rather than the pod's. The Sphinx sidecar uses about a core while cold-building its index;
  including that in a pod-wide metric added pods that each started another cold build without
  adding request capacity. Until now the HPA existed only in the cluster, reconciled by nothing.
* **The web container's CPU and memory requests are declared** in the Prod overlay, at the values
  Prod runs today (`cpu: 1`, `memory: 1092Mi`, measured on both the 1.6.0 and the rolled-back pod
  templates, so scheduling is unchanged). The HPA's `Utilization` target is a percentage of the
  container's request: no manifest here declared one, and Prod's live values survive from the
  standalone repo's pipeline through `kubectl apply`'s three-way merge. The HPA's metric therefore
  depended on the deploy path being retired, and would have resolved to `<unknown>` — holding Prod
  at `minReplicas` exactly when it needed to scale.

### Not in this release

Two mitigations belong at the ingress, not in the application, and are tracked separately:

* Turn off `proxy-next-upstream` for timeouts, so one slow request cannot become three.
* Rate-limit the scraper. It drove the whole event and will return; the application changes here
  raise the ceiling but do not remove the incentive to defend the edge.

### Required before deploying

**Nothing new.** Migrations 117, 118 and 119 are applied and verified in every environment,
including Prod — re-verified 2026-09-16 on Prod: binary rows out of threshold **0**, real
`gs_count` miscounts **0**, `production.process_thresholds` free of `ABS(`.

| | 117 | 118 | 119 |
|---|---|---|---|
| Dev | applied | applied | applied |
| SQA | applied | applied | applied |
| Stage | applied 2026-09-15 | applied 2026-09-15 | applied 2026-09-15 |
| Prod | applied 2026-09-15 | applied 2026-09-15 | applied 2026-09-15 |

Prod's JaccardSimilarity `.dat` caches were generated after the 1.6.0 deploy and live on the results
PVC, so they survive the rollback and this redeploy. **Prod is currently on the pre-1.6.0 image**, so
promoting Prod means moving it forward two releases at once — 1.6.0's application changes arrive with
1.6.1's limits.

### Known issues carried forward

* ⚠️ **A stale duplicate `public.process_thresholds` exists on Prod and SQA** (not Dev, not Stage).
  It is the **pre-117 body**: Binary as `value > threshold`, P/Q inclusive (`<=`), and type 4/5 on
  `ABS(value)` — every behaviour migrations 117 and 119 exist to remove. It predates all three
  migrations, which correctly replaced `production.process_thresholds`. The application is not
  affected: the connection pool sets `search_path TO production, extsrc, odestatic`, which does not
  include `public`. But any session that resolves `public` first — a psql session on the default
  search path, for instance — calls the unfixed function and silently rewrites membership. Needs its
  own migration to drop or redirect it; it is not addressed here because it is neither caused by nor
  fixed by this release.
* **Stage only:** 6,200 of 6,386 type-1/2 rows sitting exactly on their cutoff are flagged
  in-threshold against an exclusive procedure. SQA (0 of 28,205) and Prod (0 of 14,610) are clean.
  Pre-existing stored membership from the older inclusive Python paths; a G3-819 follow-up.
* **Prod only:** 2,956 gene sets claim genes while holding none. Migration 118 deliberately does not
  touch them — deriving the count from zero rows would zero the claim, and Tier I sets are among
  them, where lost data is likelier than a stale number. Its own ticket.
* A `NaN` threshold puts every gene in threshold (`1 < 'NaN'::numeric` is TRUE in PostgreSQL).
  Unchanged; 0 live gene sets carry one on SQA.

### Version

* `legacy/pyproject.toml` 1.6.0 → **1.6.1a**. A pre-release — the letter is what marks it — so the
  workflow deploys to **SQA only**, with no Stage/Prod promotion and no drafted GitHub release.
  Release with `git tag v1.6.1a && git push origin v1.6.1a` on the commit carrying this bump. The
  version job compares the tag against the file and fails the run if they disagree, and the bump
  alone releases nothing.
* Installs as **`1.6.1a0`** (PEP 440 normalises `a` → `a0`), verified in the release image. PEP 440
  orders `1.6.0 < 1.6.1a0`, so this is an upgrade from what SQA runs today.
* ⚠️ **Artifact identity:** this builds a *new* image, so 1.6.0's sign-off does not transfer.
  §4.3.2's TOOLBOX binary assertion needs re-running against this build.

---

## 1.6.0 — released 2026-09-15; **Prod rolled back 2026-09-16**

> **Prod is not running this version.** It was deployed to Prod at 19:38 UTC on 2026-09-15
> and rolled back at 01:48 UTC on 2026-09-16 after a site-wide outage; Prod has been serving
> the previous image (`59d15fb-dirty`) since. The outage was a request-concurrency collapse,
> not a defect in this version's application code — see **1.6.1a**, which is the redeploy
> path. SQA and Stage still run 1.6.0. All three database migrations are applied everywhere.

**The promotion release.** Not new application behaviour: 1.6.0 carries the *same application code*
as `1.6.0c`, which SQA has been running and verifying since 2026-09-14. What changes is the release
*shape* — a plain version with no letter, so the workflow promotes **SQA → Stage → Prod** and drafts
a GitHub release, instead of stopping at SQA.

> **Every deploy is still gated.** Pushing the tag queues the Stage and Prod deploy jobs behind their
> GitHub environment approvals; it does not deploy anything on its own. Nothing reaches Prod until
> someone approves it, and **Prod must not be approved until its migrations are applied** — see
> *Required before each environment* below.

### Changed since 1.6.0c

No application code. `git diff v1.6.0c..main` touches five files, none of them under `legacy/src`:

* **Prod deploy config** (`5cf51108` / #17) — the prod overlay no longer declares `spec.replicas` for
  either Deployment. Prod is the only environment with HorizontalPodAutoscalers
  (`geneweaver-legacy` min 2 / max 8, `geneweaver-legacy-tools` min 2 / max 10), and they own that
  field; the overlay's old `replicas: 4` was a value prod has never run, while the worker inherited
  the base default of 1 — one below its HPA floor. A JSON patch now removes the field so the
  autoscaler is the only writer. dev, sqa and stage still render `replicas: 1`, matching their live
  state.
* **Tooling** (#18) — `checks/gwc44-binary-threshold-drift.sql` no longer dies on its own section 3;
  an apostrophe in an `\echo` was read by psql as an opening quote.
* **Documentation** (#16, #17, #18) — the release plan's measured per-environment database state, the
  corrected `.dat` ordering, the prod HPA record, and the changelog's version-normalisation note.

### Required before each environment

Ordering is not optional: `process_thresholds` is a *database* object, so the right image with the
wrong procedure still misbehaves. Per environment, **migrations first, then the deploy**
(release plan §5.2).

| | 117 | 118 | 119 | pre-state captured |
|---|---|---|---|---|
| SQA | applied | applied | applied | — |
| Stage | applied 2026-09-15 | applied 2026-09-15 | applied 2026-09-15 | yes |
| Prod | applied 2026-09-15 | applied 2026-09-15 | applied 2026-09-15 | yes — rollback ready |

All environments are now done and verified (binary rows out of threshold 0, real `gs_count`
miscounts 0, type-4/5 disagreements 0, `ABS(` gone from `production.process_thresholds`). This table
read "Prod: NOT applied" when 1.6.0 was prepared; Prod's migrations were run on 2026-09-15 ahead of
its deploy, and re-verified 2026-09-16. See 1.6.1a's known issues for the stale
`public.process_thresholds` duplicate this re-verification turned up.

Then, **after** each environment's deploy — not before, because the generators ship inside the
monorepo-built image — generate that environment's JaccardSimilarity `.dat` caches (§4.3.3 item 3).
Stage and Prod both still need this; SQA has them and they survive pod replacement on the results
PVC.

### Known issues carried forward

* **Stage only:** 6,200 of 6,386 type-1/2 rows sitting exactly on their cutoff are flagged
  in-threshold, against a procedure that is exclusive. SQA (0 of 28,205) and Prod (0 of 14,610) are
  clean. Pre-existing and unrelated to migrations 117/118/119, none of which touches type-1/2 — it is
  stored membership from the older inclusive Python paths that `process_thresholds` has never
  recomputed. A G3-819 follow-up, not a release blocker.
* **Prod only:** 2,949 `normal`, user-visible gene sets claim genes while holding none (worst claim
  20,930), across 339 owners, none created after 2021. Migration 118 deliberately does not touch
  them — deriving a count from zero rows would zero the claim, and 886 of them are Tier I, where
  lost data is likelier than a stale number. Its own ticket, with the 2009 and 2017 clusters as the
  lead.
* A `NaN` threshold puts every gene in threshold (`1 < 'NaN'::numeric` is TRUE in PostgreSQL).
  Unchanged from 1.6.0c; 0 live gene sets carry one on SQA.

### Version

* `legacy/pyproject.toml` 1.6.0c → **1.6.0**. A full release — no letter — so the workflow promotes
  through **Stage and Prod** and drafts a GitHub release. Release with
  `git tag v1.6.0 && git push origin v1.6.0` on the commit carrying this bump; the bump alone does
  not release, and the version job fails the run if tag and file disagree.
* Installs as **`1.6.0`** with no normalisation, unlike the lettered pre-releases
  (`1.6.0a`→`1.6.0a0`, `1.6.0b`→`1.6.0b0`, `1.6.0c`→`1.6.0rc0`). PEP 440 orders `1.6.0rc0 < 1.6.0`,
  so this is an upgrade from what SQA runs today.
* ⚠️ **Artifact identity:** this builds a *new* image. SQA's 1.6.0c sign-off does not transfer to it,
  so §4.3.2's TOOLBOX binary assertion needs re-running against this build. Identity does hold
  *within* the run — one image is built and that same artifact is deployed to SQA, Stage and Prod in
  turn, with SQA re-verified as the first hop.

---

## 1.6.0c — released to SQA 2026-09-14

A single-fix pre-release: the score-type / threshold-shape crash that test **T3** of the 1.6.0b
verification pass turned up. A **pre-release, SQA only.**

> **Scope note.** No database migration is required, and no gene set's membership changes. The fix
> is preventive: 0 of 18,649 live type-1/2 gene sets on SQA held a threshold the database could not
> store, so nothing was stuck — the write is simply no longer attempted with one.

### Fixed — curation & upload

* **Changing a gene set's score type from Correlation/Effect to P-Value/Q-Value lost the change**
  (G3-823) — `ae030f83`, `07d8da7d`, `861f093e`. A curator switching from a two-sided type (whose
  threshold is a `low,high` pair) to a one-sided one (a single number) without also editing the
  threshold field got *"An unknown error ocurred."* and the save was discarded. The `UPDATE` itself
  is legal — `gs_threshold` is `character varying` — but the AFTER UPDATE trigger then runs
  `process_thresholds`, which casts the threshold: `cast(gs_threshold as numeric)` for the one-sided
  types, `string_to_array(gs_threshold, ',')::numeric[]` for the two-sided ones. The comma raises,
  the trigger aborts, and the whole statement rolls back — so the row never reached an inconsistent
  state; the defect was that the write was attempted at all with a threshold whose shape did not
  match the new type.

  Fixed on both sides. `geneweaverdb.normalize_threshold_for_type` corrects, before the write, any
  threshold the database would refuse to store — checked per component against PostgreSQL's numeric
  literal grammar (the regex migration 119 already carries) *and* numeric's declared digit limits.
  `editgenesets.html` reshapes the field when the score type changes, so the requirement is visible
  before saving rather than corrected behind the curator, and it banks the previous value per score
  type so a round trip gives it back.

  A range carries no p-value cutoff, so it is not converted: reusing the low end of `0.0,10.0` would
  cast fine and hide the crash, but a cutoff of 0 puts every gene out of threshold — a visible error
  traded for a silently emptied gene set. The type's established default is used instead (`0.05` for
  P/Q, `-1,1` for Correlation, **`-1000,1000` for Effect**, matching `batch.py`'s
  `__parse_score_type` and `uploadfiles.get_default_threshold`), and the substitution is reported
  through the `result['warnings']` channel G3-812 added, so the curator is told the cutoff they asked
  for was not the one saved.

  Pre-existing, not a 1.6.0b regression: the path arrived with `cedfee9e` (GWC-42, which made score
  type editable). 1.6.0a's C2 test missed it by exercising P-Value → Correlation, the direction that
  survives because `string_to_array('0.05', ',')` yields a one-element array and
  `BETWEEN 0.05 AND NULL` is merely NULL.

### Testing & developer tooling

* `legacy/tests/db/test_score_type_threshold_shape.py` — **39 tests**, added to the CI module list;
  suite **189**. The contract test is the load-bearing one: over a corpus of junk, whatever goes in,
  what comes out for a given score type is something that type's cast accepts.
* The client half is **executed, not inspected**. The decision is factored out of the jQuery handler
  as a jQuery-free `nextThresholdValue()`, and the tests lift it out of the template and run it under
  `node`, skipping cleanly where node is absent. Two further tests pin the form's grammar and its
  per-type defaults to the server's, so the two halves cannot drift.
* `normalize_threshold_for_type` was validated probe-by-probe against `geneweaver-sqa`
  (PostgreSQL 15.18) — 24 inputs, 0 mismatches with what the server actually does, including the
  exact bounds (`1e131071` stores, `1e131072` raises; `1e-16383` stores, `1e-16384` raises).

### Known issues

* **A `NaN` threshold puts every gene in threshold.** `1 < 'NaN'::numeric` is TRUE in PostgreSQL, and
  `numeric` accepts both `NaN` and `Infinity`, so such a threshold casts cleanly and is left
  untouched by the fix above. Correcting it would move published membership, which is a
  curation-semantics decision rather than a crash fix and wants its own measurement and approval.
  Measured while deciding: **0 live gene sets on SQA** carry one; Stage and Prod are not readable
  from here (RBAC). Not yet filed.
* Two review findings on the fix were real holes and are worth knowing about if this code is touched
  again: `float()` is not numeric's grammar (`float('1_0')` is `10.0`, `cast('1_0' as numeric)`
  raises), and JavaScript's `Number()` accepts `0x1`, so `0x1,0x2` read as a well-formed pair. Both
  are closed, and both have tests that fail if the checks are "simplified" back.

### Version

* `legacy/pyproject.toml` 1.6.0b → **1.6.0c**. A pre-release (the letter is what marks it), so the
  release workflow deploys to **SQA only**. Release with `git tag v1.6.0c && git push origin
  v1.6.0c` on the commit carrying this bump — the bump alone does not release.
* **The app footer reads `1.6.0rc0`, not `1.6.0c0`.** PEP 440 treats `c` as the canonical
  abbreviation for `rc`, so the normalisation that turned `1.6.0a` into `1.6.0a0` and `1.6.0b` into
  `1.6.0b0` turns `1.6.0c` into `1.6.0rc0`. The release is unaffected — the gate compares the tag
  against `legacy/pyproject.toml`, which holds the un-normalised `1.6.0c` — but anyone checking
  which build SQA is on should expect `1.6.0rc0`. Confirmed on the deployed 1.6.0c image. See the
  note at the top of this file: `1.6.0d` would be rejected outright, so this scheme ends here.
* **Released**: tagged `v1.6.0c` on `94490332` (the PR #15 merge) and deployed to SQA on
  **2026-09-14** (run `34855953334`), with Stage, Prod and the GitHub release draft skipped as
  designed. Verified on the running pod: image `…:9449033`, both containers ready at 0 restarts,
  the two changed runtime files byte-identical to `main`, and `normalize_threshold_for_type`
  exercised inside the deployed image across the corrected, untouched and left-alone cases.

---

## 1.6.0b — released to SQA 2026-09-08

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
* **Released**: tagged `v1.6.0b` on `b9ecbe0b` (the PR #13 merge) and deployed to SQA on
  **2026-09-08 14:35 UTC** (run `33897407803`), with Stage, Prod and the GitHub release draft
  skipped as designed. The SQA deploy sat on its approval gate for four days between the tag and
  the rollout.

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
