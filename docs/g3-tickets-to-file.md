# Jira tickets — ready to file (Atlassian MCP was disconnected 2026-09-17)

Two tickets were verified against the live databases on 2026-09-17 but could not be created:
the Atlassian connection returned `403 "The app is not installed on this instance"`. Reconnect
with `/mcp` and these can be submitted as-is.

Both: **Project** G3 · **Issue type** Bug · **Parent (epic)** G3-754 · **Components** legacy

---

## Ticket 1 — Priority: Medium

**Summary:** Stale duplicate `public.process_thresholds` on Prod and SQA carries the pre-117 body

### What is wrong

A second copy of `process_thresholds` exists in the **`public`** schema on **Prod and SQA**,
alongside the correct one in `production`. It carries the **pre-117 body** — every behaviour
migrations 117 and 119 exist to remove.

Verified directly against each database on **2026-09-17**:

| environment | schemas holding `process_thresholds` | `public` copy body |
| --- | --- | --- |
| **prod** | `production`(1), **`public`(1)** | contains `ABS(`, P/Q inclusive (`<=`) |
| **sqa** | `production`(1), **`public`(1)** | contains `ABS(`, P/Q inclusive (`<=`) |
| stage | `production`(1) | no `public` copy |
| dev | `production`(1) | no `public` copy |

The three defects in that stale body:

* **Binary** membership as `value > threshold` rather than the corrected rule (migration 117).
* **P/Q** thresholds **inclusive** (`<=`) rather than exclusive — the boundary settled on G3-809.
* **Score types 4 and 5** on `ABS(value)` rather than the signed value (migration 119).

It predates migrations 117, 118 and 119, all of which correctly replaced
`production.process_thresholds` and left this copy untouched.

### Why the application is not currently affected

The connection pool sets `search_path TO production, extsrc, odestatic`, which does **not**
include `public`. Every application path therefore resolves `production.process_thresholds`.

### Why it still needs fixing

Any session resolving `public` first calls the unfixed function — a `psql` session on the default
search path being the obvious case. `process_thresholds` **writes** `gsv_in_threshold`, so an
invocation does not fail or warn: it silently rewrites gene set membership using the rules three
migrations were written to eliminate. The next person to run a threshold recomputation from a
plain `psql` session would corrupt membership with no error and no obvious trace.

It is also a trap for exactly this area of work — the migration series deliberately converged the
divergent implementations, and this copy quietly preserves the divergence in a schema nobody
thinks to check.

### Proposed fix

Its own migration, next free number after 121, to **drop** `public.process_thresholds` where
present. Confirm before dropping rather than assuming:

* Nothing depends on it — check `pg_depend`, and grep the codebase and operational scripts for
  unqualified `process_thresholds` calls.
* Whether the intent is *drop* or *redirect*. A drop is cleanest; if any out-of-band script may
  call it unqualified, replacing the body with a thin wrapper delegating to
  `production.process_thresholds` fails safe instead of failing loudly.

Only Prod and SQA carry it, so the migration must tolerate its absence on dev and stage
(`DROP FUNCTION IF EXISTS`, and verify the signature — do not drop by name alone if overloads
exist).

### Verification

* `SELECT n.nspname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE p.proname = 'process_thresholds'`
  returns only `production` in every environment.
* `production.process_thresholds` unchanged, still post-119 (no `ABS(`, P/Q exclusive).
* No gene set's `gsv_in_threshold` changes — this removes an unused path, it recomputes nothing.

### Provenance

Found during the 1.6.1a verification pass, recorded as a known issue carried forward in
`legacy/CHANGELOG.md` under both 1.6.1a and 1.6.1, each time noting it needs its own migration.
Re-verified 2026-09-17 during the 1.6.2 release; still present, still the pre-117 body.

---

## Ticket 2 — Priority: Low

**Summary:** dev: `production.geneset_search` is missing migration 116's GIN index and is ~75% bloated

### What is wrong

Two independent problems with the same view on **dev only**, both measured 2026-09-16/17.

**1. Migration 116's GIN index is absent.** 116 creates
`CREATE INDEX geneset_search_idx ON production.geneset_search USING gin(_combined_tsvector)`.
sqa, stage and prod all have it; dev does not:

| environment | indexes on `geneset_search` | index bytes |
| --- | --- | --- |
| **dev** | `geneset_search_unique_idx` only | **5752 kB** |
| sqa / stage / prod | `geneset_search_unique_idx` + `geneset_search_idx` (GIN) | 439 MB on prod |

`GET /api/genesets/search` filters on `_combined_tsvector @@ plainto_tsquery(...)`, so on dev that
predicate has no index and falls back to a sequential scan over ~261,000 rows whose tsvector
column is TOASTed. Functionally correct, needlessly slow, and it makes dev a poor place to
measure search performance.

**2. The view is bloated and has never been vacuumed.**

| environment | rows | total size | of which TOAST | `last_autovacuum` |
| --- | --- | --- | --- | --- |
| **dev** | 261,024 | **2138 MB** | ~1856 MB | **never** |
| sqa | 261,154 | 1222 MB | ~1224 MB | never |
| prod | 264,716 | 1890 MB | 1224 MB | 2026-04-15 |

dev holds essentially the same row count as sqa in **75% more space, with fewer indexes**. Cause:
`REFRESH ... CONCURRENTLY` is a diff-and-merge and leaves dead tuples, autovacuum's trigger is
relative to table size (`50 + 0.2 × live_tuples` ≈ 52,000 rows here) so a nightly delta never
reaches it, and nothing had ever vacuumed this view.

### What is already fixed, and what is not

The nightly CronJob shipped in **1.6.2** now runs `VACUUM (ANALYZE)` after each refresh
(G3-826, PR #27), so **the bloat stops compounding** from 2026-09-17 on — confirmed on prod,
28,508 → 0 dead tuples in 16.5s. But plain `VACUUM` marks space reusable without returning it to
the OS, so the **2138 MB already on disk stays**. Reclaiming it needs `VACUUM FULL`, which takes
`ACCESS EXCLUSIVE`.

### Proposed fix

1. Create the missing GIN index on dev, matching 116 exactly.
2. `VACUUM FULL production.geneset_search` on dev in a window where locking the view is
   acceptable — dev being dev, that is cheap. Expect it to drop towards sqa's ~1222 MB.
3. Consider whether prod's 1890 MB deserves the same treatment in a real maintenance window.
   Separate call; not urgent now that the nightly vacuum holds the line.

Worth deciding whether this should be a migration or a one-off operational task. It is a *drift*
repair rather than a schema change — sqa, stage and prod already match 116 — so a migration that
recreates the index everywhere would be a no-op on three of four. A `CREATE INDEX IF NOT EXISTS`
migration is still defensible as documentation of intent.

### Why it happened, probably

The unrecorded `geneset_search_unique_idx` (present on all four, in no migration in this repo)
plus dev's missing GIN index plus the bloat together suggest the view was dropped and rebuilt by
hand on dev at some point, and refreshed repeatedly thereafter with nothing cleaning up.

### Verification

* `SELECT indexname FROM pg_indexes WHERE schemaname='production' AND tablename='geneset_search'`
  on dev lists both `geneset_search_unique_idx` and `geneset_search_idx`.
* `EXPLAIN` of the search predicate on dev shows a bitmap index scan, not a sequential scan.
* `pg_total_relation_size('production.geneset_search')` on dev is in the same range as sqa's.
