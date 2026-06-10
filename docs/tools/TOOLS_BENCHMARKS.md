# GeneWeaver Tools — Benchmarks & "is the Python implementation better?"

> Review of the ported tools against the **canonical** legacy source
> (`github.com/TheJacksonLaboratory/geneweaver-legacy-tools`, byte-identical to the
> image-recovered `legacy/tools-worker/` for every ported tool), focused on the tools whose
> port *changed the algorithm* rather than just refactoring. Benchmarks: `scripts/benchmarks/`.
> Run on the seeded local Postgres (`gw-local-pg`) + the locally-built `dbscan`/`biclique`
> binaries. **Last updated:** 2026-06-10

## Verdict summary

| Tool | What the port changed | Better than original? | Evidence |
|---|---|---|---|
| **DBSCAN** | in-process `SklearnDBSCAN` (scipy sparse + sklearn) vs. the C++ binary | **Yes — adopt as default** | identical clusters (multi-cluster, real + synthetic); **4.9×→56× faster**; removes the compiled-binary/subprocess/ARG_MAX dependency |
| **JaccardClustering** | `scipy.cluster.hierarchy` vs. hand-rolled agglomerative | **Yes** | identical merge distances (avg linkage, diff 0.0); **up to 86× faster** |
| **HyperGeometric** | `math.comb` vs. legacy incremental-float `combtl` | **Yes** | fixes the lt/tt bug + exact integers; also **1.1×–2.8× faster** |
| **PhenomeMap (KS term)** | `scipy.stats.ks_2samp` vs. legacy hand-rolled KS | **No — reverted** | scipy is **slower** (1.6×–12×) *and* changes results (exact vs. asymptotic, up to ~0.1); reverted to the faithful asymptotic KS (see below) |

The other ports (BooleanAlgebra, Combine, UpSet, JaccardSimilarity, MSET, and DBSCAN's
binary wrapper) are faithful **refactors** onto `AbstractTool` — they don't change the
algorithm, so there is no performance claim to make; they are "necessary" as framework
adapters, not "better/faster".

---

## 1. DBSCAN — in-process variant vs. the C++ binary

`SklearnDBSCAN` reproduces the legacy graph-DBSCAN (gene co-membership graph, BFS hop
radius) with a sparse eps-hop neighbour graph + `sklearn.cluster.DBSCAN(metric="precomputed")`.
The binary's `regionQuery` runs a per-seed BFS — roughly O(V·E) per seed — which scales badly.

**Agreement** (both produce the *same* clusters):
- real graph (9 sets / 70 genes), 4 (eps, minPts) settings → **identical**;
- a 3-component synthetic graph → **identical** 3 clusters `[6,6,5]`, singletons correctly
  dropped as noise, across 4 settings;
- every synthetic size below → **identical**.

**Speed** (`scripts/benchmarks/bench_dbscan.py`, eps=2 minPts=3):

| genes | sets | binary (ms) | sklearn (ms) | speedup |
|---|---|---|---|---|
| 100 | 20 | 21.9 | 4.5 | 4.9× |
| 500 | 100 | 511 | 45 | 11× |
| 1,000 | 200 | 3,591 | 211 | 17× |
| 2,000 | 400 | 26,177 | 910 | 29× |
| 5,000 | 1,000 | 351,074 | 6,229 | **56×** |

**Verdict:** the Python variant is identical in output and far faster, and it removes the
compiled-binary dependency (no cross-platform build, no subprocess, no ARG_MAX ceiling on the
serialised graph). Recommend making `SklearnDBSCAN` the default DBSCAN. *Caveat:* agreement
was verified on graphs up to 3 clusters; border-point handling on pathological graphs is not
proven bit-identical (the binary's `expandCluster` vs. sklearn density-reachability), so a
one-off spot-check against the binary is worthwhile if exact legacy parity is ever required.

## 2. JaccardClustering — scipy vs. hand-rolled

The legacy hand-rolls agglomerative clustering: each merge rescans all cluster pairs and
their members (`ward` even rebuilds TP/FP/FN over **all genes × all gene-set pairs** every
merge). The port uses `scipy.cluster.hierarchy.linkage` on the condensed Jaccard-distance
matrix (C-backed, ~O(n² log n)).

**Equivalence:** legacy `average_cluster` vs. scipy `average` linkage — merge distances
**identical** (max diff 0.0) at n = 8/12/20. The legacy `complete`/`average`/`single` are the
textbook per-member max/avg/min linkages, so scipy reproduces them; `mcquitty` = WPGMA =
scipy `weighted`. **Exception:** the legacy `ward` is *non-standard* (it recomputes Jaccard
from the merged gene union, not Lance–Williams Ward), so scipy's `ward` (the textbook one)
will differ — flagged, not a defect of the port.

**Speed** (`scripts/benchmarks/bench_jaccard_clustering.py`, method=average):

| gene sets | legacy (ms) | scipy (ms) | speedup |
|---|---|---|---|
| 50 | 7.9 | 0.8 | 9.8× |
| 100 | 60.8 | 7.5 | 8.1× |
| 150 | 196.5 | 2.0 | 99× |
| 200 | 458.2 | 5.3 | **86×** |

**Verdict:** same results (standard methods), and the legacy's super-quadratic growth makes
the port dramatically faster as gene-set count rises. Clear win.

## 3. HyperGeometric — `math.comb` vs. `combtl`

The port's main point is **correctness** — it fixes the legacy's cross-tail `pval`
accumulation bug and uses exact integer binomials (validated in
`scripts/validation/validate_hypergeometric.py`: matches the legacy where the legacy is
correct, and `scipy` where it is not). Speed was expected to be a wash or worse (bigints),
but `math.comb` (C) actually **beats** the legacy cached Python `combtl` loop:

| universe (table total) | legacy (ms) | port (ms) | ratio |
|---|---|---|---|
| 50 | 3.4 | 1.2 | 2.8× |
| 200 | 27.5 | 10.6 | 2.6× |
| 800 | 401.6 | 358.2 | 1.1× |

**Verdict:** better on both axes — correct *and* faster (until very large tables, where
bigint cost erodes the margin to ~parity). Clear win.

## 4. PhenomeMap KS term — scipy vs. hand-rolled (reverted)

The port had swapped the legacy hand-rolled two-sample KS for `scipy.stats.ks_2samp`,
documented as an "improvement". Benchmarking disproved that:

| sample n | legacy KS (ms) | scipy KS (ms) | max \|Δp\| vs legacy |
|---|---|---|---|
| 10 | 23.8 | 278.2 | 0.11 |
| 200 | 147.7 | 425.6 | 0.018 |
| 1,000 | 812.7 | 1,307.3 | 0.033 |

Two problems: scipy is **slower** (per-call overhead), and it **changes the result** —
`ks_2samp` defaults to the *exact* p-value for small samples, whereas the legacy uses an
*asymptotic* approximation (Stephens, with the `en + 0.12 + 0.11/en` correction). They differ
by up to ~0.1 for small n. `method='asymp'` is ~10× closer to the legacy but still not
identical (different asymptotic form).

**Why the earlier validation showed "max diff 0.0":** every gene in the local DB has
`gene_rank = 0.0`, so all KS inputs were identical → d=0 → p=1.0 in both implementations. The
KS term is **inert on the current data** (PhenomeMap link scores reduce to the gene-count
ratio). The 0.0-difference was real but vacuous.

**Verdict:** the scipy swap is *not* an improvement — slower and divergent from the legacy.
For a faithful migration the legacy asymptotic KS is the correct behaviour, so the port was
**reverted** to a pure-Python transcription of the legacy KS (faster than both numpy-legacy
and scipy, faithful to the original, and it removes scipy from PhenomeMap entirely). Worth
confirming with the team whether `gene_rank` is ever populated; if it stays 0.0 the KS term
never fires regardless.

---

## Reproducing

```bash
# build the binaries (macOS notes in TOOLS_MIGRATION.md §9)
(cd legacy/tools-worker/tools/TOOLBOX/biclique_tool && make)          # biclique
# dbscan: xcrun clang++ -std=c++11 -stdlib=libc++ -isysroot $(xcrun --show-sdk-path) \
#         -isystem $(xcrun --show-sdk-path)/usr/include/c++/v1 -o dbscan dbscan.cpp dbscanMain.cpp

GENEWEAVER_DBSCAN_BINARY=/path/to/dbscan GENEWEAVER_DBSCAN_GRAPH_JSON=/path/to/graph.json \
  uv run --extra sklearn --project packages/tools python scripts/benchmarks/bench_dbscan.py
uv run --extra sklearn --project packages/tools python scripts/benchmarks/bench_jaccard_clustering.py
uv run --project packages/tools python scripts/benchmarks/bench_hypergeometric.py
uv run --extra sklearn --project packages/tools python scripts/benchmarks/bench_phenomemap_ks.py
```
