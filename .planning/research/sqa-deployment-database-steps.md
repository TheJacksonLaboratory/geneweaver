# Research: Database steps for a full legacy deployment to SQA

> Question: What must be done on the database side for a full legacy deployment to
>   SQA, and where could this release introduce a regression?
> Date: 2026-08-21
> Mode: **local-only** (no web access used — every source is a file in this repo,
>   cited as `path:line`). Confidence is therefore about *what the repo asserts*,
>   plus which of those assertions I could verify mechanically here.
> Overall confidence: high on the migration mechanics; medium on completeness of
>   the verification list (see Gaps — several are demonstrably stale).

## Primary source

`docs/ci-cd/G3-781_LEGACY_RELEASE_PLAN.md` (540 lines) is the authoritative runbook.
§5 is the database work, §6 per-environment verification, §7 rollback. Everything
below is grounded there unless marked as my own check.

---

## Findings

### 1. Two migrations are pending for SQA, not one
**What:** SQA needs **117** (required) and **118** (recommended). Both are applied on
dev only. `118` is the highest-numbered migration in the tree — nothing newer has
landed since 2026-08-06, which I confirmed by listing `legacy/migration/`.

| # | File | Ticket | Status | Nature |
|---|---|---|---|---|
| 117 | `117-fix-binary-threshold-not-thresholded.sql` | GWC-44 / G3-776 | **required** | `CREATE OR REPLACE FUNCTION production.process_thresholds` + one-time backfill of `extsrc.geneset_value` |
| 118 | `118-backfill-inflated-gs-count.sql` | GWC-34 / G3-782 | **recommended** | Resets `production.geneset.gs_count` from `extsrc.geneset_value` where they disagree |

**Source:** plan §5.1 (`:300`), §5.4 (`:378`), §1 table (`:56-68`).
**Confidence:** high.
**Action:** Both. 117 is required because without it the UI upload path
(`create_geneset2` → `process_thresholds`) keeps producing unusable Binary genesets
even with the new image. 118 is not needed for code correctness — the code fixes stop
*new* drift — but without it the already-wrong genesets keep showing the old number,
which is exactly what the reporter sees.

### 2. Both migrations run BEFORE approving that environment's deploy
**What:** Ordering is load-bearing, for two different reasons.
- **117 before deploy** — plan §5.2 (`:360`): deploying the code without the migration
  leaves the UI upload path and the threshold-change trigger still broken.
- **118 before deploy** — because the deploy is what republishes the search index. The
  search sidecar runs `indexer --all` at container start, so migration-then-rollout
  gets the reindex for free.

**Source:** §5.2 (`:360`), §5.4 (`:445-455`).
**Confidence:** high.
**Action:** Sequence per environment: apply 117 → apply 118 → approve the deploy job.

### 3. The reindex trap — `gs_count` is materialised, and a delta reindex will not see it
**What:** `gs_count` is a Sphinx/Manticore index attribute (`sql_attr_uint = gs_count`),
not a live table read. Corrected values reach search only on a **full** `indexer --all`.
A *delta* run cannot pick them up: `geneset_delta_src` selects
`gs_updated >= sphinxcounters.last_update`, and 118 deliberately leaves `gs_updated`
alone (it is the geneset's user-visible last-modified time; bumping it would assert the
contents changed when only a cached total was repaired).

Verified on dev: after the backfill GS407872 read **1538** in the database while the
still-running index served **1901**.

**Source:** §5.4 (`:445-458`); migration 118's own header.
**Confidence:** high (empirically verified on dev, recorded in the plan).
**Action:** If 118 is run *without* a following deploy, restart the
`geneweaver-legacy-search` container or search keeps serving stale numbers. Confirm on
**My Genesets**, which reads `gs_count` straight from the table and is correct the moment
the migration commits — that is also the page GWC-34 was reported from.

### 4. Capture the audit table first, or the backfills are irreversible
**What:** Both migrations are idempotent; only one is reversible out of the box.
- **117** — idempotent (`CREATE OR REPLACE` + `IS DISTINCT FROM TRUE` guard). The
  function is reversible; **the backfill is not** unless the affected rows are captured
  into `production.gwc44_117_backfill_audit` *first*. The plan is blunt about this:
  "Without that audit table the backfill cannot be distinguished from legitimately
  in-threshold rows — **do not skip §5.1 step 1**."
- **118** — idempotent (only rewrites rows that currently disagree, so a second run
  matches nothing) and reversible: it captures pre-state into
  `production.gwc34_118_gs_count_audit` itself, with the rollback statement commented at
  the foot of the migration file.

**Source:** §5.1 (`:318-330`), §7 (`:500-514`), foot of `118-backfill-inflated-gs-count.sql`.
**Confidence:** high.
**Action:** Run the §5.1 sizing query, then the audit-table capture, and assert the
capture count equals the sizing count before applying 117. Keep both audit tables until
SQA is signed off.

### 5. Connection route — use the Cloud SQL Auth proxy, not `kubectl exec psql`
**What:** The `geneweaver-legacy` pods have **no psql client**. §5.4 says so explicitly
and points at the proxy instead.
**Trap:** §5.1 (`:350-356`) still offers a `kubectl -n prod exec … psql …` route for
migration 117. That command cannot work — the correction in §5.4 was never applied back
to §5.1. Anyone running the sections in order hits it.
**Source:** §5.1 (`:345-356`) vs §5.4 (`:432-436`).
**Confidence:** high (the two sections of the same document contradict each other; §5.4
is the later and correct one).
**Action:** Use `cloud-sql-proxy` + `psql -v ON_ERROR_STOP=1 -f <file>` for both
migrations. Fallback if you cannot run the proxy: drive the statements through the pod's
Python + psycopg2, which does carry the `DB_*` environment.

### 6. Detect before you apply — there is no migration ledger
**What:** I grepped for `schema_migrations` / `migration_history` / alembic / flyway /
liquibase across `legacy/`. **Nothing.** There is no table recording which migrations an
environment has. Applied state must be probed per migration.
- **118** has a purpose-built read-only report:
  `legacy/migration/checks/gwc34-gs-count-drift.sql`. Section 1 = what 118 will fix;
  section 2 = the empty-geneset population it deliberately will not; section 3 = whether
  the backfill has already run in that database. Safe to run any time, including Prod in
  hours.
- **117** has no equivalent check script; use the §5.1 step-0 sizing query, plus the
  `pg_get_functiondef(...) LIKE '%WHEN gs_threshold_type=3 THEN%TRUE%'` probe to see
  whether the procedure is already patched.

**Source:** my grep (no hits); §5.4 (`:420-430`); §5.1 (`:310-345`).
**Confidence:** high.
**Action:** Before touching SQA, run both detections to establish the baseline. Also
confirm SQA is actually current on 100–116 — nothing in the repo records that, and the
plan does not assert it.

### 7. Scale and blast radius on the shared instance
**What:** 118 aggregates `extsrc.geneset_value` once (~35M rows / ~20s on dev, 33 rows
updated) in a **single transaction**. Prod is larger. dev and SQA share Cloud SQL
`jax-dev-10-guided-jay`; Stage and Prod share `jax-prod-10-promoted-owl` — so a heavy
Stage run can affect Prod.
**Source:** §5.4 (`:438-444`), §5.1 (`:357-359`), CLAUDE.md deploy notes.
**Confidence:** high.
**Action:** SQA is the low-risk rehearsal but shares an instance with dev — expect dev
impact, not prod. **Time it on Stage before Prod.** If the transaction is too long for a
Prod window, run sizing + audit capture outside the transaction and batch the `UPDATE` by
`gs_id` range.

### 8. Not migrations, but check anyway
**What:** §5.3 (`:368`) lists three things that look like DB work and are not:
- **MSET backgrounds (GWC-45)** — dev's fix was tied to dev's Dec-2025 gene reload.
  Re-check per environment rather than assuming a refresh is needed. dev's `ode_gene_id`s
  were remapped, so compare tool output on **metrics, never raw IDs**.
- **Find Similar (GWC-35)** — the `geneset_jaccard` cache recomputes on page load. No
  migration.
- **Search (G3-778)** — Sphinx index unchanged, no reindex required *for that fix*.
**Confidence:** high.
**Note:** §5.3's "no reindex required" and §5.4's "full `indexer --all`" are scoped to
different changes but read as a contradiction on a skim. See Gap 6.

---

## Regression risks — gaps in the plan's own verification list

The user's second question ("make sure we are not adding any regression") is where this
research found real problems. §6 is a good per-fix verification table, but it was written
around 2026-08-05/06 and **four subsequent changes shipped into this release with no row
of their own**. Each is a code change that alters user-visible behaviour.

| # | Gap | Why it matters | Severity |
|---|---|---|---|
| 1 | **G3-805 homology fix has no §6 row.** `5c79bb0d` (2026-08-13) changed Find Similar to `LEFT JOIN extsrc.homology` and re-key membership. §6 only covers G3-780 (candidate-side thresholding). | This **changes user-visible Jaccard numbers** on Find Similar — measured at 8.6% of in-threshold memberships on dev, 8.4% on sqa, in *both* directions (24 inflated / 16 deflated of 40 sampled pairs). Nobody is scheduled to verify it in SQA, and it is exactly the kind of change a curator would report as a new bug. **Updated 2026-08-21:** G3-805 moved to Done, so the *ticket* gap is closed but the *verification* gap is not — §6 still has no row for it. Note every other fix in §6 is also Done in Jira and still has a row, because §6 exists to re-verify per environment: Done means tested on dev, not verified in SQA. | **High** |
| 2 | **XSS-escaping change has no §6 row.** `f11ae9fb` (2026-08-14) routed four upload-result sinks through `gwEscapeHtml`/`gwEscapeHtmlJoin`. | It altered **how upload warnings render**. The GWC-42 and GWC-36 rows check that warnings appear, but not that they still render correctly after escaping. A double-escape or a broken join would show literal `&lt;` or a collapsed message. New JS file (`static/js/geneweaver/escapeHtml.js`) must also actually be served by the release image. | **High** |
| 3 | **MSET message text changed after §6 was written.** `5651bbcd` (2026-08-14) rewrote the GWC-51 background message to add the "contact the GeneWeaver team" direction. | §6's GWC-51 row describes the *old* expected text. A tester following it may pass a message that no longer matches, or flag the new sentence as unexpected. | Medium |
| 4 | **Help-link repoint has no §6 row.** `5a712ad8` points `/help/`, the header "?", the footer, and the frontpage panel at the monorepo docs site. | Harmless in SQA, **prod-blocking**: the monorepo is internal, so its Pages site is org-only and external users would hit an org login. Tracked as release gate B9 — but B9 lives in `LEGACY_CICD_MIGRATION.md`, not in §6, so a §6-driven sign-off will not surface it. | Medium (High at Prod) |
| 5 | **§3 release mechanics goes stale the moment PR #6 merges.** §3 states the trigger is "push to `main` that touches `legacy/pyproject.toml`" and §4.2 says "Merge PR #2 — this *is* the release trigger". PR #6 (`ci/legacy-release-on-tag`, head `d4601cdc`, **open**) replaces that with `on: push: tags: ['v*.*.*']` plus a tag-vs-pyproject equality check. | If PR #6 merges first, **merging PR #2 will no longer release anything** — someone must push a `v1.6.0` tag. §2's "hold the merge, not just the deploy" rationale also evaporates. Conversely if PR #2 merges first, §3 is still correct. The plan does not mention PR #6 at all. I confirmed `main` today still carries the old trigger, so §3 is accurate *right now*. | **High** (sequencing) |
| 6 | **§5.1 tells you to run 117 via `kubectl exec … psql`.** The pods have no psql client; §5.4 corrects this but only for 118. | A reader working through §5 in order hits a command that cannot work. Wastes a maintenance window. | Medium |
| 7 | **Test-gate count is stale in two places.** §3 says "the 42 unit tests", §1 says "48 unit tests". I counted the 9 modules enumerated in `_legacy-tests.yml`: **89**. | Cosmetic for the deploy, but it is the number a reviewer uses to sanity-check that the gate ran everything. And the gate **enumerates modules rather than discovering them** (a known anti-pattern here) — so a new test file is silently skipped. | Low |
| 8 | **Duplicate migration numbering.** `114-add-sso-id-to-user-table.sql` collides with `114-create-view-geneset2hom.sql`, and `115-create-view-geneset2hom.sql` is **byte-identical** to the 114 one (verified with `diff`). | Harmless if applied (idempotent view creation), but it means "apply everything after N" by filename order is ambiguous. Relevant only if SQA's baseline turns out to be behind. | Low |

---

## Recommended SQA database sequence

Condensed from §5, with the traps above already routed around.

```bash
# 0. Baseline — read-only, safe any time.
cloud-sql-proxy <project>:<region>:jax-dev-10-guided-jay --port 5433 &
psql "host=127.0.0.1 port=5433 dbname=geneweaver-sqa user=<admin>" \
     -f legacy/migration/checks/gwc34-gs-count-drift.sql        # 118 detection
#    + §5.1 step-0 sizing query and the pg_get_functiondef probe  # 117 detection
```

1. **Confirm the DB name and admin role.** Still an open decision (§8.6): who holds the
   role that can `CREATE OR REPLACE` in `production`.
2. **Migration 117** — size it, capture `production.gwc44_117_backfill_audit`, assert the
   capture count equals the sizing count, apply with `-v ON_ERROR_STOP=1`, then verify
   `should_be_zero` = 0 and `proc_patched` = true.
3. **Migration 118** — apply with `-v ON_ERROR_STOP=1`. It captures its own audit table.
4. **Approve the SQA deploy** — the rollout restarts the search sidecar, which runs
   `indexer --all` and republishes corrected `gs_count` values.
5. **Verify** — walk §6, and add the four missing rows from the gap table above.
6. **Keep both audit tables** until SQA is signed off.

## Summary

SQA needs **two** migrations, in order, **before** the deploy is approved: 117
(required — the Binary-threshold procedure plus a backfill that is irreversible unless
you capture the audit table first) and 118 (recommended — the `gs_count` backfill, which
is self-auditing and reversible). Use the Cloud SQL Auth proxy, not `kubectl exec psql`;
the pods have no psql client, and §5.1 still tells you otherwise. Run the migrations
before approving the deploy so the rollout's `indexer --all` republishes corrected
`gs_count` — a delta reindex cannot see the change.

On regressions: the migration mechanics are in good shape, but §6's verification list has
not kept up with the branch. Four changes merged after it was written — the **G3-805
homology fix** (which measurably moves Find Similar's Jaccard numbers), the **XSS-escaping
change** (which altered upload-message rendering), the **MSET message rewrite**, and the
**Help-link repoint** — have no verification row. The homology and escaping gaps are the
two I would not ship to SQA without adding.

## Open questions (need human judgment)

1. **PR #6 vs PR #2 merge order.** If the tag trigger lands first, §3/§4.2 are wrong and
   merging PR #2 releases nothing. Which merges first, and who updates §3?
2. **Is SQA current on migrations 100–116?** Nothing in the repo records applied state,
   and no ledger exists. Needs an empirical check before assuming 117/118 are the only gap.
3. **DB names and the admin role** — §8.6, still open.
4. ~~**Does the plan's §2 gate still hold?**~~ **ANSWERED 2026-08-21 (Jira checked).**
   The §2 gate is **clear**. All ten GWC tickets are Done, the G3-769 umbrella is Done, and
   as of 2026-08-21 all of the release's code tickets are Done. The only G3 item still open is
   a follow-up, not release content:
   - ~~G3-805~~ **moved to Done 2026-08-21T16:15Z.** The release's code work is now
     entirely Done. This does **not** close Gap 1: §6 still has no verification row for the
     homology fix, and Done-on-dev is the same state every other §6 row is in.
   - **G3-770 — `To Do`.** NCBO key removal/rotation, still open as §8.4 ("ship the
     hardcoded key to prod, or land the secret first?"). The rotation is now known to have a
     **second site** — `legacy/curation-server/ncbo.py:29` hardcodes the same key with no env
     override — so the ticket as scoped is incomplete.
   G3-781 (the release itself) is `In Progress`. §1's "Jira status (2026-08-05)" column is
   therefore stale everywhere and should be re-read from the board, not the document.
5. **Migration 117 sizing on SQA is unknown.** The plan gives dev numbers for 118 (~35M
   rows / ~20s) but no row count for 117 in any environment.
