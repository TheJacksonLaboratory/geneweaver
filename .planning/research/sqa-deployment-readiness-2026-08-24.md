# Research: What is the next step to deploy legacy 1.6.0 to SQA (migrations included)

> Question: I am trying to deploy to SQA. What is the next step needed to do it
>   successfully, database migration included?
> Date: 2026-08-24
> Mode: **live-state verification.** Supersedes the numbers in
>   `.planning/research/sqa-deployment-database-steps.md` (2026-08-21), which was
>   read out of the docs. Everything below was probed against the running SQA
>   cluster and the `geneweaver-sqa` database, or against `main` / the GitHub API.
> Overall confidence: high — every claim is an observation, and the command that
>   produced it is named.

## Short answer

**The next step is G3-806: apply migrations 117 and 118 to `geneweaver-sqa`.**
Nothing else blocks it, and the three things the release plan lists as open
questions for that step are all now answered (§2). Then push `v1.6.0`, assert the
TOOLBOX binaries on the freshly built image, and approve the SQA gate.

The release has **not started**: there is no `v1.6.0` tag, and no tag of any kind
exists on the remote.

---

## 1. Where the release actually stands

| Fact | Value | How verified |
|---|---|---|
| `main` | `89891aae`, in sync with origin | `git rev-parse HEAD origin/main` |
| `legacy/pyproject.toml` | **1.6.0** — already matches the tag to push | `grep ^version` |
| Tags on remote | **none at all** | `git ls-remote --tags origin` (empty), `gh api .../tags` (empty) |
| `legacy-release.yml` runs | **one**, the cancelled 2026-08-14 run `31839201644` | `gh run list --workflow legacy-release.yml` |
| GitHub releases | none | `gh release list` |
| SQA web image | `…/docker/geneweaver/geneweaver-legacy:e4e52e5-dirty` | `kubectl -n sqa get deploy` |
| SQA worker image | `…/docker-dev/geneweaver-legacy-tools:555b16a-dirty` | same |
| G3-806 / 807 / 808 | **Sprint Ready** (none started) | Jira |
| G3-781 | In Progress | Jira |

So SQA is still serving the standalone repo's build, and the trigger is a
deliberate `git tag v1.6.0 && git push origin v1.6.0` (workflow `on: push: tags:
['v*.*.*']`, confirmed on `main`).

## 2. The three "open decisions" blocking G3-806 are answered

§8.6 of the release plan lists DB name, admin role and connection route as open.
All three resolve for SQA:

### 2.1 Database identity
`geneweaver-sqa` on Cloud SQL `jax-dev-10-guided-jay`, **PostgreSQL 15.18**.
Connection name for the proxy: `jax-compsci-nc-dev-01:us-east1:jax-dev-10-guided-jay`.
Verified with `gcloud sql instances list` / `gcloud sql databases list` and by
connecting: `current_database() = geneweaver-sqa`.

### 2.2 The role — no separate admin account is needed
The application's own role **`geneweaver-sqa` owns
`production.process_thresholds`**, holds `CREATE` on schema `production`, and is
a member of `cloudsqlsuperuser`. It can apply both migrations as-is.

```
current_user / session_user   geneweaver-sqa / geneweaver-sqa
is superuser                  False
can CREATE in schema production   True
member of function owner role     True
roles granted                 cloudsqlsuperuser
search_path                   "$user", public, production, extsrc, odestatic, curation
```

### 2.3 Connection route — simpler than the plan says
`kubectl exec` **works on SQA**, and the pod carries Python + psycopg2 + the
`DB_*` environment. No Cloud SQL proxy and no local credentials are required:

```bash
kubectl -n sqa exec -i deploy/geneweaver-legacy -c geneweaver-legacy -- python - < script.py
```

The plan's warning still holds — the pods have **no psql client**, so §5.1's
`kubectl exec … psql` route cannot work. `cloud-sql-proxy` and `psql` *are*
installed locally if the proxy route is preferred, but it is not needed.

## 3. Migration state on SQA — probed, since there is no ledger

### 3.1 SQA is current on 100–116
Every object those migrations create is present, so 117/118 really are the only
gap. Probed by object existence, not by a ledger (there is none):

| Migration | Probe | Present |
|---|---|---|
| 109 | `production.geneset_is_readable2()` | ✅ |
| 110 | `production.geneset2ontology` table | ✅ |
| 111 | `production.notifications.dismissed` | ✅ |
| 112 | `production.create_geneset_for_queue()` | ✅ |
| 113 | `odestatic.tool_param` CS_Mset rows (4: Background/NumberofSamples/NumberofTrials/Species) | ✅ |
| 114 | `production.usr.usr_sso_id` | ✅ |
| 114/115 | `extsrc.geneset2hom` materialized view | ✅ |
| 116 | `production.geneset.gs_tsvector`, `geneset_fts_idx`, `production.publication.pub_tsvector` | ✅ |

This closes open question 2 of the 2026-08-21 research doc.

### 3.2 Migration 117 (GWC-44) — NOT applied. Small.
The live procedure still carries the pre-fix binary branch:

```
gs_threshold_type=3 THEN
        gsv.gsv_value>cast(gsvt.gs_threshold as numeric)
```

Sizing (`extsrc.geneset_value` ⋈ `production.geneset`, 61s, one seq scan of
34.1M rows): **5,956 rows across 22 binary genesets.** The backfill itself is
trivial — seconds, not a maintenance window. `production.gwc44_117_backfill_audit`
does not exist yet, so §5.1 step 1 has not been done.

### 3.3 Migration 118 (GWC-34) — NOT applied. Bigger than dev, but almost all of it is invisible.
`production.gwc34_118_gs_count_audit` absent. Drift check section 1:

| | SQA (today) | dev (before its 2026-08-06 run) |
|---|---|---|
| genesets wrong | **807** | 33 |
| phantom genes | 5,178,672 | 1,792 |
| worst single | 2,328,373 | — |
| under-counted | **422** | **0** |

Two things there deserve attention, and characterising them **lowers** the risk
rather than raising it.

**(a) 118's own header says under-counting does not happen.** It asserts "All
three can only over-count… on dev no geneset is under-counted." On SQA 422 of
807 are under-counted, so 118 will *raise* `gs_count` for them — a direction the
plan never reviewed. The migration handles it correctly anyway (the predicate is
`IS DISTINCT FROM`, and it sets `gs_count = real_rows` either way), and the
population is benign: **all 422 are 2012-era `deprecated:*` HPO phenotype sets
with a gap of 1–4 genes.** None is user-visible.

**(b) Only 12 of the 807 are user-visible.** Breakdown by status:

| Status | over-counted | under-counted |
|---|---|---|
| `deleted` | 326 (incl. the 2.3M-gap `gurab_gene_error_*` pairs) | 0 |
| `deprecated:*` | 47 | 422 |
| **`normal`** | **12** (worst gap 177) | 0 |

So on SQA, 118 is a near-cosmetic cleanup of deleted and deprecated rows — not
the headline user-facing fix it was on dev. Still worth applying (consistency,
and it is what the reporter's My Genesets page reads), but it is not what makes
or breaks SQA sign-off.

Section 2 (empty genesets 118 deliberately leaves alone) is 3,040 `normal` /
8,254 `deleted` / ~900 `deprecated`, worst live claim 20,930 — same shape as dev
(2,920 normal). Expected; not a failure.

## 4. Pre-flight: what is already clean for SQA

`kubectl -n sqa diff` against `kubectl kustomize deploy/k8s/overlays/jax-cluster-dev-10--sqa`
shows **only** the image placeholders (skaffold substitutes them), the
`skaffold.dev/run-id` labels, and two new env vars on the worker. ConfigMaps,
PVC, ExternalSecret and Ingress are byte-identical to live.

- **§4.3.5 Auth0 — non-issue.** The rendered `AUTH_CLIENTID`
  (`x9IiBRyt8lS3lsqrz2H6aO1leRBbxyb7`) equals SQA's live configmap value exactly.
  SQA inheriting the base value is *already* the live state; the deploy changes
  nothing. No login break.
- **Replica counts — non-issue for SQA.** Rendered 1/1 = live 1/1. The web 2→4 /
  tools-worker 2→1 risk in the risk register is **prod-only**.
- **Namespace prerequisites — all present.** `geneweaver-db` (4 keys), `redis`,
  `geneweaver-legacy-secrets` (ExternalSecret `SecretSynced=True`),
  `geneweaver-pvc` Bound 100Gi RWX. Ingress host `geneweaver-sqa.jax.org` matches.
- **Test gate is current.** All 9 modules `_legacy-tests.yml` enumerates exist,
  and no `legacy/tests/test_*.py` is missing from the list (the three DB-backed
  suites are excluded deliberately). The enumerate-don't-discover anti-pattern is
  still there, but it is not stale right now.
- **New on the worker:** the deploy adds `TOOLS={"tool_dir":"/app/tools-worker/tools","results":"/var/geneweaver/results"}`
  and `APPLICATION_RESULTS=/var/geneweaver/results`. The tool directory moves from
  `/app/src/tools` to `/app/tools-worker/tools`, so the §6 "one tool per family"
  check matters.

## 5. §4.3.3 (`genes.dat` / `homology.dat`) — a pre-existing defect on SQA, NOT a release regression

The plan flags these as possibly missing from the new image. They are — and it
turns out **they are already missing on SQA today**, which reclassifies the item.

`gw_dist_data_dir()` (`legacy/tools-worker/tools/TOOLBOX/distribution_generator/db_conn.h:38`)
resolves to `$GW_DIST_DATA_DIR`, else `$APPLICATION_RESULTS/dist_data`, else
`/var/geneweaver/results/dist_data`. On SQA:

- `/var/geneweaver/results/dist_data/` holds **no `.dat` files**, and neither does
  the results root.
- The running `555b16a-dirty` worker has them at `/app/src/tools/TOOLBOX/distribution_generator/`
  — but at **134 and 132 bytes**, because they are **unresolved Git LFS pointer
  files** (`version https://git-lfs.github.com/spec/v1 / oid sha256:… / size 154071680`).
  The real 154 MB file was never fetched.
- That directory also contains **no compiled binary** — `distribution_generator.o`
  was never built in the old image (the other seven TOOLBOX binaries are present).

So the consumer of these files — JaccardSimilarity's p-value fallback
(`JaccardSimilarity.py:99`, which only fires when `extsrc` has no cached frequency
row for that set-size pair) — is **already broken on SQA** and will be no worse
after the release. `distribution_generator.cpp:384-388` prints "genes.dat failed
to open." and `return -1`; the Python does `subprocess.Popen(...).wait()` without
checking the exit code and then re-reads an empty table.

**Conclusion: do not hold the SQA deploy for this.** It deserves its own ticket.

**Two corrections to the plan's remedy**, for whoever picks that ticket up:
1. The plan says `fileGenerator -g -h`. **That cannot work** —
   `fileGenerator.cpp:103-115` reads only `argv[1]`, so `-h` is ignored. It needs
   two separate runs.
2. The binary is installed as **`file_generator.o`** (makefile `install` target),
   not `fileGenerator`.
3. `genes.dat` is one line per `geneset_value` row of non-deprecated genesets
   (~35M lines). Per CLAUDE.md, generate to local disk and bulk-copy — point
   `GW_DIST_DATA_DIR` at `/tmp/dist_data`, then one `cp` to the GCSFuse-backed PVC.

## 6. Recommended SQA sequence

```bash
# 1. G3-806 — migrations. No proxy needed; the pod role owns the function.
#    Run 117's audit capture and the migration, then 118.
kubectl -n sqa exec -i deploy/geneweaver-legacy -c geneweaver-legacy -- python - < apply-117.py
kubectl -n sqa exec -i deploy/geneweaver-legacy -c geneweaver-legacy -- python - < apply-118.py

# 2. Start the release. pyproject.toml is already 1.6.0, so the version job will pass.
git tag v1.6.0 && git push origin v1.6.0

# 3. The run stops at "Legacy Deploy: SQA" awaiting a reviewer. BEFORE approving,
#    assert the TOOLBOX binaries on the *freshly built* image (§4.3.2) -- the
#    release rebuilds into the prod registry, so dev's result does not carry over.
#    Expect mset/ to be absent; that is correct.

# 4. Approve SQA. The rollout restarts the search sidecar, which runs
#    `indexer --all` and republishes corrected gs_count.

# 5. Verify §6 plus the four rows it is missing (see §7 below).
#    Keep both audit tables until SQA is signed off.
```

Ordering constraints, both load-bearing:
- **117 before the deploy** — the code alone leaves `create_geneset2` →
  `process_thresholds` still producing unusable Binary sets.
- **118 before the deploy** — `gs_count` is a materialised Sphinx attribute
  (`sql_attr_uint`), and a *delta* reindex cannot see the change (`geneset_delta_src`
  filters on `gs_updated`, which 118 deliberately leaves alone). The rollout's
  `indexer --all` is what publishes it. Run 118 without a following deploy and
  search keeps serving stale numbers until the sidecar restarts.

Execution notes on the migration files themselves:
- **117 has no transaction wrapper** (118 does — `BEGIN`/`COMMIT` around steps 0–3).
  Wrap it, or run it with `psql -1`. The two statements are a `CREATE OR REPLACE
  FUNCTION` and a 5,956-row `UPDATE`, so the window is small either way.
- **117 step 1's audit capture is not in the migration file** — it is in the plan
  (§5.1). Without it the backfill is irreversible, because backfilled rows become
  indistinguishable from legitimately in-threshold ones. Capture, then assert the
  count equals 5,956, then apply.
- 118 captures its own audit table and carries its rollback statement at the foot
  of the file.

## 7. Verification gaps that still stand

The 2026-08-21 research doc's regression findings are unaffected by anything
above and remain the right list. §6 of the plan has **no verification row** for
four changes that merged after it was written:

1. **G3-805 homology fix** (`5c79bb0d`) — measurably moves Find Similar's Jaccard
   scores (8.4% of in-threshold memberships on sqa), in both directions. This one
   will look like a new bug to a curator if nobody is expecting it.
2. **XSS-escaping change** (`f11ae9fb`) — altered how upload warnings render;
   confirm `static/js/geneweaver/escapeHtml.js` is actually served (404 = broken
   warnings).
3. **MSET message rewrite** (`5651bbcd`) — §6's GWC-51 row describes the old text.
4. **Help-link repoint** (`5a712ad8`) — harmless on SQA, prod-blocking (org-only
   Pages site). Tracked as B9 in `LEGACY_CICD_MIGRATION.md`, which a §6-driven
   sign-off will not surface.

Add rows 1 and 2 before SQA sign-off; 3 and 4 are text/prod-gate issues.

## Summary

The next step is the SQA database work (G3-806), and it is fully unblocked: the DB
is `geneweaver-sqa` on `jax-dev-10-guided-jay`, the app's own role owns the
function and can apply both migrations, and `kubectl exec` + psycopg2 reaches it
without a proxy. SQA is current on 100–116; 117 and 118 are both unapplied. 117 is
5,956 rows across 22 binary genesets. 118 is 807 genesets — 25× dev — but only
**12** are user-visible, and the 422 under-counted rows that contradict the
migration's own header are all deprecated 2012 HPO sets with 1–4 gene gaps.

Two plan items downgrade on inspection: SQA's Auth0 client ID and replica counts
are already what the overlay renders, so the deploy changes neither. And the
missing `genes.dat`/`homology.dat` is a **pre-existing** SQA defect — the running
worker holds unresolved Git LFS pointers and never built
`distribution_generator.o` — so it should not hold the deploy, but it needs its
own ticket, and the plan's `fileGenerator -g -h` remedy is wrong on both the
binary name and the flags.

## Open questions (need human judgment)

1. **Apply 118 to SQA at all?** Only 12 user-visible genesets benefit. Applying it
   keeps environments consistent and rehearses the Prod run; skipping it avoids
   touching 795 deleted/deprecated rows. Recommendation: apply — the rehearsal
   value before Stage/Prod is the real point.
2. **Who approves the SQA environment gate?** Still §8.5, unresolved.
3. **`genes.dat` ticket owner.** Pre-existing, but the release is when the tool
   directory moves, so it is a natural moment to fix it.
4. **Uncommitted `legacy/tests/test_search_filters.py`** in the working tree adds
   76 lines covering the third G3-778 bug (the `STATUS`-guard regression). It will
   **not** ship with `v1.6.0`. Commit it first, or accept that the tag's gate does
   not cover that bug.
