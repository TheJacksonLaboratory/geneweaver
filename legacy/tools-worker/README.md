# Legacy GeneWeaver Tools Worker (recovered source)

This is the source for the **`geneweaver-legacy-tools`** Celery worker — the service that
actually executes the GeneWeaver analysis tools. The legacy Flask app (in `../src`)
dispatches jobs to this worker via Celery (`toolcommon.celery_app.send_task(...)`).

## Provenance — why this is here
At recovery time this source appeared to be **not in version control**: the production
worker image (`us-docker.pkg.dev/jax-cs-registry/docker/geneweaver-legacy-tools:555b16a-dirty`)
was built from an **uncommitted working tree**, and commit `555b16a` could not be found in
the repos then accessible (`geneweaver-legacy`, all branches, checked). The image looked like
the only copy, so it was recovered by extracting `/app/src/tools` from the **prod** image
(digest `sha256:f4aea726a6b452b877cf664faba7030f9f78a7392e393e4b286b811910bdd35a`) and
committed here (read-only registry pull; no impact on the running worker).

**Update (2026-06):** the canonical **`geneweaver-legacy-tools`** GitHub repo
(`github.com/TheJacksonLaboratory/geneweaver-legacy-tools`) *does* have `555b16a` as its
`HEAD` (the `G3-712-ABBA-Tiers` merge) — so the gap is closed: the source is git-tracked there.
A full tree diff confirms this recovered copy is **byte-identical** to that repo for all
Python tools (the 14 tool modules + `toolbase`/`celeryapp`/`config`) and the `TOOLBOX` C/C++
*source*; the only differences are build artifacts (`*.o`, ELF binaries) and large `*.dat`
data — i.e. the `-dirty` delta in the image did not touch the tool source. This copy is kept
as a self-contained, in-monorepo reference snapshot.

## Contents
- `tools/celeryapp.py` — the Celery app (`geneweaver.tools`) that registers each tool task.
- `tools/toolbase.py` — `GeneWeaverToolBase(Task)`: shared DB access, gene-set matrix
  construction, pairwise-deletion, progress reporting, and the `run()` / `mainexec()` contract.
- `tools/<Tool>.py` — one Celery task per tool: `JaccardSimilarity`, `JaccardClustering`,
  `PhenomeMap`, `ABBA`, `DBSCAN`, `MSET`, `BooleanAlgebra`, `TricliqueViewer`, `UpSet`,
  `Combine`, `GeneSetViewer`, `SimilarGenesets`, `HyperGeometric`, `ProcessLargeGeneset`.
- `tools/TOOLBOX/` — C/C++ compute backends the Python tools shell out to via `subprocess`
  (`biclique`, `bicliquer`, `bk-partite`, `DBSCAN`, `mset`, `CS_Mset`, `CS_Boolean`,
  `distribution_generator`, ...). Build with `make` in each subdirectory.

## Excluded from git (build artifacts / large data — not source)
- Compiled artifacts: `*.o` and the ELF binaries (`dbscan`, `biclique`, `bicliquer`,
  `bk-partite`, ...). Rebuild via `make` in each `TOOLBOX/<tool>` dir.
- Large runtime data: `TOOLBOX/distribution_generator/genes.dat` (~147 MB) and
  `homology.dat` (~1.7 MB) — sourced at runtime; available in the worker image if needed.

## Status
Preserved here as the recovered **source of truth** the reimplementation was validated
against. The next-generation port lives in the monorepo:
- **`packages/tools`** — 9 tools on the `AbstractTool` framework (BooleanAlgebra, Combine,
  JaccardSimilarity, DBSCAN, HyperGeometric, JaccardClustering, UpSet, MSET, PhenomeMap).
- **`packages/db`** — ABBA & SimilarGenesets (DB query/aggregation, not in-memory tools).
- **Flagged / not ported** — GeneSetViewer (UI rendering), TricliqueViewer (incomplete
  scaffold), PhenomeMap permutation add-on.

See `docs/tools/TOOLS_MIGRATION.md` and `docs/tools/TOOLS_BENCHMARKS.md` for the per-tool
status, validation against this source, and benchmarks.
