# G3-781 — Legacy Release Plan (dev → SQA → Stage → Prod)

> **Ticket:** [G3-781](https://jacksonlaboratory.atlassian.net/browse/G3-781) (High, To Do) —
> promote the G3-769 legacy bug fixes from dev through SQA → Stage → Prod, and move
> ownership of those environments' legacy deploys from the standalone `geneweaver-legacy`
> repo to the monorepo's `legacy-release.yml`.
>
> **Umbrella:** [G3-769](https://jacksonlaboratory.atlassian.net/browse/G3-769) · **PR:** [#2](https://github.com/TheJacksonLaboratory/geneweaver/pull/2) (open, MERGEABLE, all checks green)
> **Branch:** `fix/G3-769-legacy-bug-fixes-and-improvements` · **Version:** `legacy/pyproject.toml` 1.5.27 → **1.6.0**
> **Status:** DRAFT — not started. Blocked on curation-scientist testing (§2) and the standalone-pipeline freeze (§4.1).
> **Last updated:** 2026-08-04
>
> Background on the pipelines themselves: `docs/ci-cd/current-monorepo-cicd/LEGACY_CICD_MIGRATION.md`.

---

## 1. What is being promoted

All of it is **on dev only** today — but it is **not** just the G3-769 branch.

⚠️ **Scope correction (2026-08-05).** An earlier version of this section said "one commit range:
`origin/main..fix/G3-769-…` (20 commits)". That understates the release by about half, because
**two** sets of legacy changes reach SQA/Stage/Prod for the first time in this release:

1. **The G3-769 bug fixes** — 20 commits, on the branch, **not** merged (PR #2 is still open).
   These are the per-fix table below.
2. **Migration-era legacy work** — 21 further `legacy/` commits that are **already on `main`**,
   merged by the earlier **G3-748 monorepo-migration PR** *before* this branch was cut off it.

Set 2 is easy to miss precisely because it is already merged: it does not appear in
`origin/main..<branch>`. But SQA/Stage/Prod have never had it — they still run builds from the
standalone `geneweaver-legacy` repo — and the release builds from the **merge commit on `main`**,
so it carries both sets: roughly **41 legacy commits**, not 20. (The table below already cites two
of set 2 — `1ad89158` and `b82688d1` — which is why its rows did not match the "20 commits" claim.)

```bash
git rev-list --count origin/main..fix/G3-769-legacy-bug-fixes-and-improvements -- legacy/  # 20 (set 1)
git log --oneline --since=2026-06-01 origin/main -- legacy/                                # 21 (set 2)
```

The already-in-`main` set is substantial and mostly **untested by the §6 list below** — it includes
MSET Python 2→3 fixes (`fa492116`), an MSET worker crash / wrong list-2 background (`1ecba34a`), a
DBSCAN no-clusters crash (`bd30502b`), graphviz `dot` resolution (`7416c3dc`), the Auth0
client-secret logging fix (`69d86897`), tools-worker containerisation (`c3b1b489`), its k8s
Deployment (`348c2cfd`), and env-driven TOOLBOX DB connections + the libpqxx 6.4.8 pin
(`14359acb`). Several are tools-worker changes, which is the same component §4.3.1 flags as
first-time-managed-by-the-monorepo — so this is where the release risk actually concentrates.
**Before approving SQA, walk that list and decide what needs verifying**; the per-fix table below
covers the branch work only.

| Ticket | Fix | Commits | Jira status (2026-08-05) | DB change |
|---|---|---|---|---|
| G3-765 / GWC-50 | BooleanAlgebra Symmetric-Difference 500 + Venn blanking | `1ad89158`, `3d1f67b9` | Done | — |
| G3-766 / GWC-45 | MSET stale-background subset error | `b82688d1` | Done | dev-only data refresh (§5.3) |
| G3-767 / GWC-8 | Annotation generator broken since ~Jun 2025 | `456d0147`, `c2be6326` | Done | — |
| G3-768 / GWC-36 | Genes silently dropped on upload (alias symbols) | `4680637b`, `519d45a1` | **Ready for Testing** | — |
| G3-772 / GWC-42 | Score-type validation + editable score type | `cedfee9e`, `53c29cfd`, `e07015e0` | Done | — |
| G3-775 / GWC-9 | Admin-page tier change; geneset edit view | `35e47977` | Done | — |
| G3-776 / GWC-44 | Binary gene sets thresholded → unusable in tools | `2e737f01` | **Ready for Testing** | ⚠️ **migration 117** |
| G3-778 | Search robustness (3 bugs) | `4fee2bb4` | **Ready for Testing** | — |
| G3-780 / GWC-35 | Find Similar thresholds only one side | `ac0a986c` | **Ready for Testing** | — |
| G3-779 | Regression suite (48 unit tests) + legacy CI gate | `f7196d77`, `e3d6fdde`, `3908c1cd` | In Progress | — |
| G3-782 / GWC-34 | Inflated `gs_count` — geneset edit / delayed upload, **plain UI upload**, and tool-generated genesets | `a133bd2b`, `3908c1cd`, `3ddd38a5` | In Progress | **migration 118** (§5.4); applied to dev 2026-08-06, pending SQA/Stage/Prod |
| G3-783 / GWC-51 | MSET cryptic error for Tier-IV genesets outside the background | `0ba54c0a` **(set 2 — already in `main`)** | In Testing | — |

Also on the branch and shipping with it: version bump to 1.6.0 (`e888036d`), the batch paste-box
upload improvement (`29b9338b`), gitignore/CLAUDE.md chores, and the G3-770 NCBO-key TODO doc
(`53731db1`).

## 2. Release gate — testing not finished

Four of the fixes are **Ready for Testing** and awaiting the curation scientist (Tessa); three are
actively being tested. **Do not start §4 until those come back Done.** If one fails, it is far
cheaper to fix it before the first monorepo legacy release than to hot-fix across three
environments afterwards.

Recommended: hold the merge (not just the deploy). See §4.2 for why merging is itself the release
trigger.

## 3. Release mechanics (as actually configured)

`.github/workflows/legacy-release.yml`:

- **Trigger:** push to `main` that touches **`legacy/pyproject.toml`**. Nothing else fires it.
- **Version logic:** reads `tool.poetry.version`; skips if tag `legacy-v<version>` already exists;
  a version containing a letter (`1.6.0a0`) ⇒ **pre-release ⇒ SQA only**; a plain version
  (`1.6.0`) ⇒ **full ⇒ SQA → Stage → Prod** + a **draft** GitHub release tagged `legacy-v1.6.0`.
- **Jobs:** `version` → `test` (`_legacy-tests.yml`, the 42 unit tests) → `build` → `deploy_sqa`
  → `deploy_stage` → `deploy_prod` → `release`.
- **One artifact, promoted:** `build` runs `skaffold build` once against the **prod** registry
  `us-docker.pkg.dev/jax-cs-registry/docker/geneweaver` and each deploy consumes the same
  `build.json`. Images: `geneweaver-legacy` and `geneweaver-legacy-tools`, tagged with the
  abbreviated **merge-commit** SHA.
- **Approval gates:** every deploy job runs under a GitHub environment with `required_reviewers`
  — `jax-cluster-dev-10--sqa`, `jax-cluster-prod-10--stage`, `jax-cluster-prod-10--prod`. Nothing
  reaches an environment without a human approving that specific job.
- **Deploy mechanism:** `skaffold deploy --profile <environment> --build-artifacts=build.json`
  → kustomize overlay `legacy/deploy/k8s/overlays/<environment>` (namespaces `sqa`, `stage`, `prod`).

⚠️ **The dev image is not the release image.** `legacy-pull_requests.yml` builds dev into the
**test** registry (`us-east1-docker.pkg.dev/.../docker-test/geneweaver`). The release rebuilds from
the merge commit into the prod registry. Same code, a **different, freshly built image** — so the
image-level checks in §4.3 must run against the release build, not against what dev has been running.

## 4. Sequence

### 4.1 Freeze the standalone pipeline — hard prerequisite

`geneweaver-legacy`'s `release.yml` triggers on push to `main` touching `pyproject.toml`, and
deploys to the **same** GitHub environment names / clusters / namespaces (`jax-cluster-dev-10--sqa`,
`jax-cluster-prod-10--stage`, `jax-cluster-prod-10--prod`). Both repos sit at **1.5.27**. If both
pipelines stay live, the next version bump in either repo double-deploys SQA/Stage/Prod.

```bash
# 1. Announce the freeze to the team (no more releases from the standalone repo).
# 2. Disable the workflow (reversible, no commit needed):
gh workflow list -R TheJacksonLaboratory/geneweaver-legacy
gh workflow disable "Build, Deploy and Release" -R TheJacksonLaboratory/geneweaver-legacy
gh workflow list -R TheJacksonLaboratory/geneweaver-legacy   # confirm: disabled_manually
# 3. Follow up with a commit on that repo that comments out the `on: push` trigger and
#    adds a README banner pointing at the monorepo, so the freeze survives a UI re-enable.
```

Keep the standalone repo **deployable-in-anger** (workflow re-enable is one click) until prod has
run on the monorepo build for a few days.

### 4.2 Merge PR #2 — this *is* the release trigger

PR #2 changes `legacy/pyproject.toml` (1.5.27 → 1.6.0). **Merging it to `main` immediately starts a
full release run** — tests, build, then SQA/Stage/Prod deploy jobs queued behind their reviewer
gates. There is no separate "start the release" action.

Two ways to run it:

| | **A — merge as-is (recommended)** | **B — pre-release first** |
|---|---|---|
| How | Merge 1.6.0; the run stops at *Legacy Deploy: SQA* awaiting approval; approve one stage at a time | Amend to `1.6.0a0` before merge → SQA only; validate; bump to `1.6.0` in a follow-up PR for Stage+Prod |
| Artifact | **One image promoted** to all three envs (what the workflow is designed for) | SQA validates image X; Stage/Prod get a **different** image Y (rebuilt at the second bump) |
| Cost | A run sits pending-approval, possibly for days | Two runs, two builds, extra PR |

Take **A**: the approval gates already give per-environment control, and artifact identity through
prod is worth more than avoiding a pending run. Use B only if you want SQA to bake for a while
without a prod-bound run open.

Either way: **do not approve any deploy job until §4.3 and §5 are done for that environment.**

### 4.3 Pre-flight checks (before approving SQA)

1. **Tools-worker ownership — the biggest unknown.** The monorepo's kustomize base includes
   `tools-worker-configmap.yaml` + `tools-worker-deployment.yaml` (Deployment
   **`geneweaver-legacy-tools`**). The standalone repo's manifests contain **no** tools-worker at
   all — prod's worker has been running the separately built
   `geneweaver-legacy-tools:555b16a-dirty` image. So this release is the **first time the monorepo
   manages the worker in a shared environment**. Determine per namespace whether this *replaces* the
   running worker or *adds a second consumer of the same Celery queue*:

   ```bash
   for ns in sqa stage prod; do
     echo "== $ns"
     kubectl -n $ns get deploy -o wide | grep -i tool
     kubectl -n $ns get deploy geneweaver-legacy-tools \
       -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}' 2>/dev/null
     kubectl -n $ns get deploy -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.annotations.kubectl\.kubernetes\.io/last-applied-configuration}{"\n"}{end}' | cut -c1-160
   done
   ```

   **ANSWERED — measured 2026-08-04 across all four environments:**

   | env | Deployment | replicas | image | created |
   |---|---|---|---|---|
   | dev | `geneweaver-legacy-tools` | 1 | `docker-test/…:d65f790` | 2026-06-29 |
   | sqa | `geneweaver-legacy-tools` | 1 | `docker-dev/…:555b16a-dirty` | 2024-06-18 |
   | stage | `geneweaver-legacy-tools` | 1 | `docker/…:555b16a-dirty` | 2024-06-18 |
   | prod | `geneweaver-legacy-tools` | **2** | `docker/…:555b16a-dirty` | 2024-06-18 |

   **Every environment already runs a Deployment with exactly the name the monorepo's kustomize base
   uses.** So this is a **replacement in place** (rolling update onto the new image) everywhere —
   *not* a second consumer of the Celery queue. The duplicate-worker risk is retired; no scale-to-0
   step is needed. No other GeneWeaver worker Deployment exists in any namespace (the other
   `*-worker` deployments belong to unrelated services).

   This also corrects the assumption above: the standalone repo ships no tools-worker manifests, yet
   all four namespaces have one — so they were created by some other route (most likely a manual
   apply when the worker was split out in June 2024). Nothing has been reconciling them since.

   ⚠️ **New risk this surfaced — the deploy will change replica counts in prod.** The manifests do
   not match what is live:

   ```
   base/deployment.yaml               replicas: 1     base/tools-worker-deployment.yaml  replicas: 1
   overlays/…--prod/deployment.yaml   replicas: 4     (no overlay patches the tools-worker)
   live prod                          web = 2         tools = 2
   live stage                         web = 1         tools = 1
   ```

   Deploying prod as configured would take **web 2 → 4** and **tools-worker 2 → 1** — silently
   halving analysis-job throughput, because no overlay patches the worker's replica count and the
   base default of 1 wins. Decide before approving Prod: either add a `replicas: 2` (or higher)
   patch for `geneweaver-legacy-tools` to the prod overlay, or accept the reduction deliberately.
   Confirm the web 2 → 4 increase is intended too — the overlay asks for 4, but prod has been
   running 2, so the standalone repo has not been applying that value.

2. **TOOLBOX binaries actually built.** `legacy/tools-worker/Dockerfile` wraps each `make` in
   `|| echo "WARN: make failed in $d"` — exactly the swallow-the-build-failure pattern CLAUDE.md
   warns about. A missing binary produces a green build and a runtime failure.

   As of the dev build on 2026-07-30 (run `30553972874`) the swallow fires for **exactly one**
   directory — `mset/`, whose Makefile still compiles from a hardcoded prod-server path
   (`/srv/geneweaver/website-py/src/tools/mset/mset.cpp`). Nothing references it: `MSET.py:43` uses
   `CS_Mset/`. All seven binaries the tools actually exec build cleanly. So the trap is **latent,
   not active** — but the release rebuilds a *fresh* image (§3), so re-verify against the
   **release-built** image rather than trusting dev's:

   ```bash
   IMG=us-docker.pkg.dev/jax-cs-registry/docker/geneweaver/geneweaver-legacy-tools:<sha>
   docker run --rm --platform linux/amd64 --entrypoint bash "$IMG" -c '
     cd /app/tools-worker/tools/TOOLBOX; rc=0
     for b in biclique_tool/biclique DBSCAN/dbscan CS_Mset/MSETcpp bstrap/bstrap \
              bicliquer/bicliquer bk-partite/bk-partite distribution_generator/distribution_generator.o; do
       if [ ! -x "$b" ]; then echo "MISS  $b"; rc=1
       elif [ "$(head -c4 "$b" | od -An -tx1 | tr -d " \n")" != "7f454c46" ]; then echo "NOTELF $b"; rc=1
       else echo "OK    $b"; fi
     done; exit $rc'
   ```

   Paths are the ones grepped out of `tools/*.py`, not guesses — two are counter-intuitive:
   MSET lives in **`CS_Mset/`** (there is no `MSET/`), and `JaccardSimilarity.py:99` execs
   **`distribution_generator.o`**, which despite the extension is a fully linked executable (its
   makefile's `install` target compiles straight to that name). The ELF-magic check catches a stale
   host-built Mach-O that survived the strip step, which a bare `-x` test would pass.

   Any `MISS`/`NOTELF` is a release blocker. `mset/` is *expected* to be absent — do not add it.
   Worth folding this same assertion into the Dockerfile as a follow-up so CI fails instead of
   warning; note that simply dropping the `||` would break the build on `mset/`, so the fix has to
   be an artifact assertion, not fail-on-first-make-error.

3. **`genes.dat` / `homology.dat` are not in the image.** They are untracked (~147 MB / ~1.7 MB), so
   they are absent from the build context and from the new image; the old `555b16a-dirty` prod image
   had them. `distribution_generator` / `drone` / `fileGenerator` read them from
   `gw_dist_data_dir()`. Confirm per environment that this directory is a mounted volume that already
   holds them (and not a path inside the image), or regenerate them (`fileGenerator -g -h`) before
   any tool that depends on them is exercised. Generate on local disk and bulk-copy if the target is
   a GCSFuse mount (CLAUDE.md).

4. **Namespace prerequisites exist** (the manifests assume them; they are not created by this deploy):

   ```bash
   for ns in sqa stage prod; do
     echo "== $ns"
     kubectl -n $ns get secret geneweaver-db redis geneweaver-legacy-secrets 2>&1 | tail -n +1
     kubectl -n $ns get pvc geneweaver-pvc
     kubectl -n $ns get externalsecret geneweaver-legacy-secrets
   done
   ```

5. **Overlay sanity.** `sqa` inherits the **base** `AUTH_CLIENTID` (only `dev`, `stage`, `prod`
   patch a configmap; sqa patches only ingress + PVC). Confirm that is intentional for SQA's Auth0
   tenant before deploying, and diff the rendered manifests against what is live:

   ```bash
   cd legacy && for e in jax-cluster-dev-10--sqa jax-cluster-prod-10--stage jax-cluster-prod-10--prod; do
     kubectl kustomize deploy/k8s/overlays/$e > /tmp/rendered-$e.yaml; done
   kubectl -n sqa diff -f /tmp/rendered-jax-cluster-dev-10--sqa.yaml   # repeat per env/context
   ```

6. **G3-770 (NCBO key) decision.** The NCBO API key is still hardcoded in legacy (the GWC-8 fix kept
   it deliberately, to avoid re-breaking dev). Shipping 1.6.0 puts it in the prod image. Either accept
   it for this release and keep G3-770 as the follow-up, or pull the key into the
   `geneweaver-legacy-secrets` external secret first. Decide **before** approving Prod, and record the
   decision here.

### 4.4 Approve, environment by environment

For each of SQA → Stage → Prod, in order:

1. Apply migration 117 to that environment's database (§5.1) — **before** the deploy.
2. Approve the deploy job in the Actions run.
3. Watch the rollout, then run that environment's verification list (§6).
4. Only then move to the next environment.

```bash
gh run list -R TheJacksonLaboratory/geneweaver --workflow legacy-release.yml -L 5
gh run watch <run-id> -R TheJacksonLaboratory/geneweaver
kubectl -n <ns> rollout status deploy/geneweaver-legacy --timeout=5m
kubectl -n <ns> rollout status deploy/geneweaver-legacy-tools --timeout=5m
kubectl -n <ns> get deploy -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.template.spec.containers[*].image}{"\n"}{end}'
```

### 4.5 After Prod

- Publish the drafted GitHub release `legacy-v1.6.0` (`gh release list -R …`, then `gh release edit legacy-v1.6.0 --draft=false`).
- Make the standalone freeze permanent (commit + README banner, §4.1).
- Update `CLAUDE.md`: the guardrail "the monorepo currently owns **dev** for legacy; sqa/stage/prod
  are still deployed by the standalone repos" becomes untrue.
- Jira: G3-781 → Done; move the Ready-for-Testing children to Done; note the release version and
  per-env migration timestamps on G3-769 and G3-776.

## 5. Database work

### 5.1 Migration 117 (GWC-44) — required in SQA, Stage, Prod

`legacy/migration/117-fix-binary-threshold-not-thresholded.sql` does two things:
(1) `CREATE OR REPLACE FUNCTION production.process_thresholds` so `gs_threshold_type = 3` (Binary)
is always in-threshold, and (2) a one-time backfill of existing binary sets
(`UPDATE extsrc.geneset_value … WHERE gs_threshold_type = 3 AND gsv_in_threshold IS DISTINCT FROM TRUE`).

Applied to the **dev** DB only so far. Databases (per G3-781 — **confirm names before running**):
`geneweaver-sqa` on Cloud SQL `jax-dev-10-guided-jay` (shared instance with dev, separate database),
`geneweaver-stage` and `geneweaver-prod` on `jax-prod-10-promoted-owl`.

**Idempotent?** Yes — `CREATE OR REPLACE` plus an `IS DISTINCT FROM TRUE`-guarded update. Re-running
is safe. **Reversible?** The function is (§7); the backfill is **not**, unless the affected rows are
captured first. So:

```sql
-- 0) Size it first (prod may be large; if this is in the millions, batch by gs_id).
SELECT count(*) AS rows_to_change, count(DISTINCT gv.gs_id) AS binary_sets
FROM extsrc.geneset_value gv
JOIN production.geneset gs ON gs.gs_id = gv.gs_id
WHERE gs.gs_threshold_type = 3 AND gv.gsv_in_threshold IS DISTINCT FROM TRUE;

-- 1) Capture the pre-state so the backfill can be undone (do this in every environment).
CREATE TABLE IF NOT EXISTS production.gwc44_117_backfill_audit AS
SELECT gv.gs_id, gv.ode_gene_id, gv.gsv_in_threshold AS prev_in_threshold, now() AS captured_at
FROM extsrc.geneset_value gv
JOIN production.geneset gs ON gs.gs_id = gv.gs_id
WHERE gs.gs_threshold_type = 3 AND gv.gsv_in_threshold IS DISTINCT FROM TRUE;
SELECT count(*) FROM production.gwc44_117_backfill_audit;   -- must equal step 0

-- 2) Apply.
\i legacy/migration/117-fix-binary-threshold-not-thresholded.sql

-- 3) Verify: no binary set has an out-of-threshold value, and the proc is the new one.
SELECT count(*) AS should_be_zero
FROM extsrc.geneset_value gv
JOIN production.geneset gs ON gs.gs_id = gv.gs_id
WHERE gs.gs_threshold_type = 3 AND gv.gsv_in_threshold IS DISTINCT FROM TRUE;

SELECT pg_get_functiondef('production.process_thresholds(bigint)'::regprocedure) LIKE '%WHEN gs_threshold_type=3 THEN%TRUE%' AS proc_patched;
```

Connecting (either route):

```bash
# Cloud SQL Auth proxy
cloud-sql-proxy jax-.../<region>/jax-prod-10-promoted-owl --port 5434 &
psql "host=127.0.0.1 port=5434 dbname=geneweaver-prod user=<admin>" \
  -v ON_ERROR_STOP=1 -f legacy/migration/117-fix-binary-threshold-not-thresholded.sql

# or through a pod that already has DB_* env (no proxy, no local creds)
kubectl -n prod exec -it deploy/geneweaver-legacy -- bash -lc \
  'PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USERNAME -d $DB_NAME -v ON_ERROR_STOP=1 -f /dev/stdin' \
  < legacy/migration/117-fix-binary-threshold-not-thresholded.sql
```

Run it inside a transaction on Stage/Prod and time it; if the row count is large, batch by `gs_id`
to keep WAL and lock duration bounded — note that Stage and Prod share one Cloud SQL instance, so a
heavy Stage run can affect Prod.

### 5.2 Order matters

Deploying the code without the migration leaves the **UI upload path** (`production.create_geneset2`
→ `process_thresholds`) still producing unusable binary sets, and the trigger on threshold change
too. The Python-side fixes (`batch.BatchReader.__check_thresholds`,
`geneweaverdb.recompute_geneset_value_thresholds`) ship in the image. Apply the migration **before**
approving each environment's deploy.

### 5.3 Not migrations, but check

- **MSET backgrounds (GWC-45)** — the dev fix included a background regeneration tied to dev's
  Dec-2025 gene reload. SQA/Stage/Prod match their own shipped backgrounds; re-check per environment
  rather than assuming a refresh is needed (and note dev's remapped `ode_gene_id`s: compare tool
  output on metrics, never raw IDs).
- **Find Similar (GWC-35)** — the `geneset_jaccard` cache recomputes on page load. No migration.
- **Search (G3-778)** — Sphinx index unchanged; no reindex required. Confirm the search sidecar
  (`geneweaver-legacy-search`, second container in the web Deployment) comes up healthy after rollout.

### 5.4 Migration 118 (GWC-34) — `gs_count` backfill, recommended in SQA, Stage, Prod

`legacy/migration/118-backfill-inflated-gs-count.sql` resets `production.geneset.gs_count` from the
rows actually present in `extsrc.geneset_value`, for genesets where the two disagree.

Not required for the code to be correct — the code fixes stop *new* drift — but without it the
genesets that are already wrong keep displaying the old number, which is exactly what the reporter
sees. Apply it per environment alongside the deploy.

**What it corrects:** genesets that hold at least one gene but whose stored count is wrong.
**What it deliberately does not touch:** genesets with `gs_count > 0` and *zero* gene rows. Those are
a separate, unresolved problem (source files uploaded comma-separated where TSV was expected;
identifiers for species whose gene data is not loaded) and re-running the resolver restores nothing —
verified on dev. Zeroing them would change what search returns, so it is a pending product decision.
See the CHANGELOG "Known issues".

**Status by environment**

| Env | Applied | Result |
|---|---|---|
| dev (`geneweaver-dev`) | **2026-08-06** | 33 genesets corrected, 1,792 phantom genes removed; GS407881 9 → 4. Verified 0 remaining |
| sqa (`geneweaver-sqa`) | not yet | |
| stage (`geneweaver-stage`) | not yet | |
| prod (`geneweaver-prod`) | not yet | |

**1 — Detect first (read-only, safe any time, including Prod in hours)**

```bash
cloud-sql-proxy <project>:<region>:<instance> --port 5433 &
psql "host=127.0.0.1 port=5433 dbname=<db> user=<admin>" \
     -f legacy/migration/checks/gwc34-gs-count-drift.sql
```

Section 1 of that report is the number migration 118 will fix; section 2 is the empty-geneset
population it will not; section 3 says whether the backfill has already run in that database. The
same script is how you detect a **recurrence** later — if section 1 is non-zero in an environment
where 118 has already run, do not just re-run the backfill: check that the deployed image actually
contains the `uploadfiles.py` / `genesetblueprint.py` fixes first, or it will drift straight back.

**2 — Apply**

```bash
psql "host=127.0.0.1 port=5433 dbname=<db> user=<admin>" \
     -v ON_ERROR_STOP=1 -f legacy/migration/118-backfill-inflated-gs-count.sql
```

Note the `geneweaver-legacy` pods have **no psql client**, so the `kubectl exec … psql` route used
for migration 117 in §5.1 does not work for this one. Use the proxy, or drive the statements through
the pod's Python + psycopg2 (the pod does carry the `DB_*` environment).

**Scale.** The migration aggregates `extsrc.geneset_value` once (~35M rows / ~20s on dev; Prod is
larger). It runs as a single transaction. Time it on Stage before Prod — Stage and Prod share the
Cloud SQL instance `jax-prod-10-promoted-owl`, so a long Stage run can affect Prod. If the
transaction is too long for a Prod maintenance window, run the sizing and audit-capture steps
outside the transaction and batch the `UPDATE` by `gs_id` range.

**Idempotent?** Yes — it only rewrites rows that currently disagree, so a second run matches nothing.
**Reversible?** Yes — step 1 captures pre-state into `production.gwc34_118_gs_count_audit`; the
rollback statement is at the foot of the migration file. Keep the audit table until the environment
has been signed off.

**Ordering.** `gs_count` reaches search through the Sphinx/Manticore index, not the table. The search
sidecar runs `indexer --all` at pod start, so run the migration **before** approving that
environment's deploy and the rollout republishes the corrected numbers. My Genesets reads the table
directly and updates immediately.

## 6. Per-environment verification (do all of these in each env)

| Fix | Check | Pass |
|---|---|---|
| GWC-44 / G3-776 | Upload a small **Binary** geneset → its genes show in-threshold; run it through a tool (e.g. Jaccard/BooleanAlgebra) and get a non-empty result. Also open a pre-existing binary set and confirm the backfill made it usable | |
| GWC-9 / G3-775 | Admin page: change a geneset's tier (e.g. IV → III) and reload; open the edit view of a geneset that previously 500'd | |
| GWC-42 / G3-772 | Upload with an out-of-range/invalid score value → warning shown, not silent; change score type on an existing set | |
| GWC-36 / G3-768 | Batch-upload a list containing alias-only symbols (e.g. a known lncRNA alias) → all genes stored, count matches input | |
| GWC-8 / G3-767 | Geneset → generate annotations → NCBO terms returned (no traceback in logs) | |
| G3-778 | Search a term with **zero** results (no 500 from `/searchFilter.json`); apply a sort; apply a filter with an empty facet → results not zeroed | |
| GWC-35 / G3-780 | Find Similar Genesets on a thresholded set → candidate list reflects candidate-side thresholding (spot-check one candidate's in-threshold count) | |
| GWC-50 / G3-765 | BooleanAlgebra Symmetric Difference on 3+ sets → 200 + Venn diagram renders | |
| GWC-45 / G3-766 | MSET run on two same-species sets → completes without "not a subset of its background" | |
| GWC-51 / G3-783 | MSET on a **Tier-IV** set whose genes fall outside the curated background → a readable message naming the count and the offending genes, **not** a generic 500 with raw C++ stderr. Note the expected outcome is the clear error, *not* a successful run — MSET still refuses such sets by design (dev reference: GS218676 + GS407805, 63 of 5,319 genes outside the background) | |
| G3-782 / GWC-34 | Three paths, all must agree with the geneset page: (a) **plain upload** — upload a list ending in a newline that contains a couple of identifiers GeneWeaver won't recognise → My Genesets shows the number *stored*, not the number submitted (expect it to be **lower** than your input; that is correct); (b) **edit** — submit an alias and its official symbol for the same gene; (c) **tool output** — create a geneset from e.g. BooleanAlgebra Union. Then run `legacy/migration/checks/gwc34-gs-count-drift.sql` → section 1 reports 0. Pre-existing genesets stay wrong until migration 118 runs (§5.4) | |
| Worker health | `kubectl -n <ns> logs deploy/geneweaver-legacy-tools --tail=100` — worker registered its tasks, no import/binary errors | |

Log check after each rollout:

```bash
kubectl -n <ns> logs deploy/geneweaver-legacy --tail=200 | grep -iE "traceback|error|critical" | head
kubectl -n <ns> logs deploy/geneweaver-legacy-tools --tail=200 | grep -iE "traceback|error|not found" | head
```

## 7. Rollback

**Code / image** (fastest, per namespace):

```bash
kubectl -n <ns> rollout undo deploy/geneweaver-legacy
kubectl -n <ns> rollout undo deploy/geneweaver-legacy-tools    # or scale to 0 and re-enable the old worker
kubectl -n <ns> rollout status deploy/geneweaver-legacy
```

If the monorepo build itself is the problem, re-enable the standalone workflow (§4.1) and release
1.5.28 from there — which is why the freeze stays reversible until prod has been stable for a few days.

**Migration 117** — two steps, in this order:

```sql
-- 1) Restore the previous binary branch of the stored procedure: re-run the function body from
--    migration 117 with the type-3 branch changed back to
--    `gsv.gsv_value > cast(gsvt.gs_threshold as numeric)` (the pre-fix expression, quoted in the
--    migration's own comment at lines 43-47).

-- 2) Restore the backfilled rows from the audit table captured in §5.1.
UPDATE extsrc.geneset_value gv
SET gsv_in_threshold = a.prev_in_threshold
FROM production.gwc44_117_backfill_audit a
WHERE gv.gs_id = a.gs_id AND gv.ode_gene_id = a.ode_gene_id;
```

Without that audit table the backfill cannot be distinguished from legitimately in-threshold rows —
**do not skip §5.1 step 1**.

## 8. Open decisions

1. **Release shape** — A (merge 1.6.0, gate on approvals) or B (`1.6.0a0` to SQA first)? §4.2.
2. **Standalone freeze timing** — disable before merging PR #2 (recommended) or before approving SQA?
3. **Tools-worker in shared envs** — replace the existing prod worker with the monorepo-built image
   in this release, or deploy web-only first and cut the worker over separately? (Kustomize base
   includes it, so "web-only" would need a temporary overlay exclusion.) §4.3.1
4. **NCBO key (G3-770)** — ship the hardcoded key to prod, or land the secret first? §4.3.6
5. **Maintenance window** — Prod deploy + migration timing, and who approves the environment gates.
6. **DB names/credentials** — confirm `geneweaver-sqa` / `geneweaver-stage` / `geneweaver-prod` and
   who holds the admin role that can `CREATE OR REPLACE` in `production`.

## 9. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Double-deploy from both pipelines | Medium | High | §4.1 freeze before merge |
| Tools-worker duplicated in prod (two workers racing the queue) | ~~Medium~~ **None** — measured 2026-08-04: all four namespaces already run a Deployment of the same name, so this is a replace-in-place | High | Resolved; §4.3.1 |
| Prod replica counts change on deploy: tools-worker **2 → 1**, web **2 → 4** | High — this is what the manifests say today | High (worker throughput halves) | §4.3.1 — patch the prod overlay or accept deliberately, **before** approving Prod |
| A TOOLBOX binary silently missing (`\|\| echo WARN`) | Low — dev build `30553972874` shows all 7 required binaries compiling; only unused `mset/` fails | High | §4.3.2 assert on the release image (the release rebuilds, so dev's result does not carry over) |
| `genes.dat`/`homology.dat` missing from the new image | Medium | Medium | §4.3.3 confirm mount / regenerate |
| Migration 117 slow or lock-heavy on the shared prod instance | Low | Medium | §5.1 size first, batch, transaction |
| Backfill not reversible | Low | High | §5.1 audit table |
| SQA inherits base `AUTH_CLIENTID` | Low | Medium | §4.3.5 confirm intended |
| A Ready-for-Testing fix fails curation testing after release | Medium | Medium | §2 hold the merge until testing is Done |
