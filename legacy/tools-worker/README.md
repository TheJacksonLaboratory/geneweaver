# Legacy GeneWeaver Tools Worker (recovered source)

This is the source for the **`geneweaver-legacy-tools`** Celery worker — the service that
actually executes the GeneWeaver analysis tools. The legacy Flask app (in `../src`)
dispatches jobs to this worker via Celery (`toolcommon.celery_app.send_task(...)`).

## Provenance — why this is here
This source was **not in version control**. The production worker image
(`us-docker.pkg.dev/jax-cs-registry/docker/geneweaver-legacy-tools:555b16a-dirty`) was built
from an **uncommitted working tree** — commit `555b16a` exists in no repo or branch
(`geneweaver-legacy`, all branches, checked). The image was the only copy of this code.

It was recovered by extracting `/app/src/tools` from the **prod** image
(digest `sha256:f4aea726a6b452b877cf664faba7030f9f78a7392e393e4b286b811910bdd35a`) and
committed here to close that gap (read-only registry pull; no impact on the running worker).

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
Preserved here as the recovered **source of truth** for the running tools. The
next-generation reimplementation onto the `geneweaver-tools` `AbstractTool` framework
lives in `packages/tools` (in progress).
