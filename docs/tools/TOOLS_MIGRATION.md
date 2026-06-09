# GeneWeaver Tools — Migration & Reimplementation

> **Scope:** migrate the legacy GeneWeaver analysis tools onto the modern
> `geneweaver-tools` `AbstractTool` framework (`packages/tools`), as faithful, pure,
> testable reimplementations — decoupled from the legacy DB/Celery/file plumbing.
>
> **Status:** 9 compute tools ported; 1 moved to the DB layer; 2 documented as data-layer;
> 2 flagged (presentation / incomplete). **`packages/tools` unit suite: 73 passing.**
> **Last updated:** 2026-06-09

---

## 1. Background

The legacy tools are **Celery worker** tasks (`legacy/tools-worker/tools/*.py`, recovered
from the prod image — see `legacy/tools-worker/README.md`). Each subclasses
`GeneWeaverToolBase`, fetches data from the GeneWeaver DB, runs an algorithm (sometimes a
compiled `TOOLBOX/` C/C++ binary), and writes results consumed by the legacy UI.

The target is `geneweaver-tools` (`packages/tools`), whose `AbstractTool` defines:
`run(tool_input: ToolInput) -> ToolOutput`, plus `tool_input` / `tool_output` schema
properties. The reimplementations follow consistent principles:

- **Pure `run()`** — DB access (resolving gene-set memberships, homologs, etc.) is the
  caller's responsibility and is passed in via the typed `ToolInput`. Tools do not touch
  the DB or Celery.
- **Presentation dropped** — venn-circle geometry, SVG/HTML/PNG/PDF rendering, and
  table/label markup are UI concerns and are not part of the tool.
- **Faithful** — algorithms are ported faithfully from the recovered source; deliberate
  deviations (bug fixes, library swaps) are documented per tool.

## 2. Porting patterns

| Pattern | When | How / testing |
|---|---|---|
| **Pure-Python** | the algorithm is plain Python | port the logic into `run()`; caller supplies data via `ToolInput`; test `run()` directly |
| **Binary wrapper** | the real compute is a `TOOLBOX` C/C++ binary | pure `encode`/`decode` functions + an **injectable runner** (`Tool(runner=…)`); default runner subprocesses the binary at a configurable path / env var; unit-test encode/decode + `run()` with a fake runner |
| **Data-layer** | the "tool" is really a DB query/aggregation, not an in-memory algorithm | does **not** become an `AbstractTool`; lives in `geneweaver-db` as a versioned query |
| **In-process variant** | a binary algorithm has a good C-backed library | optional `[sklearn]` extra (scipy/scikit-learn); avoids subprocess + serialization overhead |

## 3. Tool status

### Ported to `packages/tools` (`AbstractTool`)

| Tool | Module | Pattern | Notes / improvements |
|---|---|---|---|
| BooleanAlgebra | `boolean_algebra` | pure | union/intersect/except over homolog groups |
| Combine | `combine` | pure | gene × gene-set membership matrix + homology merge |
| JaccardSimilarity | `jaccard_similarity` | pure | Jaccard coefficient + empirical p-value (null distribution supplied as input; the `distribution_generator` binary is a data-prep step, not per-run compute) |
| HyperGeometric | `hypergeometric` | pure | Fisher's exact (odds ratio + ut/lt/tt + hg). **Fixes a real bug**: legacy reused `pval` across the three tails (they accumulated). Uses `math.comb`. Verified vs `scipy.stats.fisher_exact`. |
| JaccardClustering | `jaccard_clustering` | pure (`[sklearn]`) | hierarchical dendrogram. **Improvement**: `scipy.cluster.hierarchy` (C-backed, ~O(n² log n)) vs legacy hand-rolled O(n³); methods ward/complete/average/mcquitty→weighted/single |
| DBSCAN | `dbscan` | binary wrapper | encode bipartite gene graph → `dbscan` C++ binary → decode JSON clusters. Also an in-process `sklearn_tool.SklearnDBSCAN` variant (`[sklearn]`) — see §5. |
| UpSet | `upset` | pure | intersection sizes per exact gene-set combination (legacy `os.system` calls were commented out) |
| MSET | `mset` | binary wrapper | wraps `MSETcpp` (Monte-Carlo enrichment); injectable runner. **Bug fix**: legacy used `group_1_background` for both lists. |
| PhenomeMap | `phenome_map` | binary wrapper (+ pure pipeline) | maximal-biclique intersection graph. `build_edge_list`/`parse_bicliques` (pure) wrap the `biclique` C binary via an injectable runner; the subset-link + scoring pass, p-value/FDR trim, cut-depth, and unconnected-node trim are pure; optional bootstrap reduction via a second injectable runner. **Improvement**: KS term uses `scipy.stats.ks_2samp` (only when ranks supplied) vs the legacy hand-rolled KS. All rendering (dot/graphml/svg/pdf/csv/json, graphviz) dropped; permutation add-on (`bicliquer`) deferred — see §5.1. |

### Moved to the data layer (not an `AbstractTool`)

| Legacy tool | Where it went | Why |
|---|---|---|
| SimilarGenesets | `geneweaver-db`: `geneset_jaccard.calculate_jaccard()` + `query/geneset_jaccard.py` | No in-process algorithm — it triggers the `calculate_jaccard` Postgres stored proc + timestamp/cache bookkeeping (one set vs all ~50k, over 2M+ memberships). Ported the stored proc to a versioned, testable query; heavy set-work stays in Postgres. A pure-Python port would be a perf/memory regression. |
| ABBA | (recommended: `geneweaver-db`) | DB query/aggregation: temp table of input genes → joins to find gene sets → tier/species count rollups. No self-contained algorithm; belongs in the data layer, not the tools framework. |

### Flagged — not yet ported (with reason + approach)

| Legacy tool | Category | Reason / approach |
|---|---|---|
| TricliqueViewer | binary (incomplete) | Legacy is a **scaffold**: reads a pre-built `.kel` edge list, runs `bk-partite`, dumps raw stdout; the JSON/CSV result generation is an unimplemented TODO and the I/O contract is undefined. Needs the `.kel` + `bk-partite` output formats specified before a faithful port. |
| GeneSetViewer | presentation | Builds a graph and renders it via graphviz `dot` (`os.system`). This is **visualization**, not a compute algorithm — belongs in the UI/rendering layer. The graph-building could be a pure helper if needed. |

## 4. Bug fixes & improvements made during the port

- **HyperGeometric (Fisher's exact)** — fixed the cross-tail `pval` accumulation bug (each
  tail now independent); switched the binomial coefficient to exact `math.comb`. Two-tailed
  output verified against `scipy.stats.fisher_exact`.
- **JaccardClustering** — replaced the legacy O(n³) hand-rolled agglomerative clustering with
  `scipy.cluster.hierarchy` (correct + C-backed).
- **MSET** — fixed the copy-paste bug where `group_2` used `group_1_background`.
- **PhenomeMap** — KS term of the link score uses `scipy.stats.ks_2samp` (well-tested,
  C-backed) instead of the legacy hand-rolled KS approximation; the whole graph pipeline
  (subset links, transitive reduction, p-value/FDR trim, cut/trim) is pure and unit-tested
  with an injectable biclique runner — no compiled binary needed for tests.
- **DBSCAN (in-process variant)** — added `SklearnDBSCAN` and a benchmark (§5).
- **dead/conflicted code** — excluded the unparseable `jaccardsimilarityblueprint2.py`
  (merge-conflict marker) from lint; dropped vendored/compiled artifacts from version control.

## 5. DBSCAN: subprocess binary vs. in-process (C-libs)

`SklearnDBSCAN` (`dbscan/sklearn_tool.py`, `[sklearn]` extra) reproduces the legacy graph
DBSCAN (gene co-membership graph + BFS hop radius) in-process: a **sparse eps-hop neighbour
graph** (bounded sparse matrix powers) → `sklearn.cluster.DBSCAN(metric="precomputed")`. No
process spawn, no serialise-the-whole-graph-into-one-argv (the binary's argv string exceeds
the 256 KB single-arg limit at ~5k genes and the ~1 MB total `ARG_MAX` at 10k → the binary
call would fail there).

Benchmark (`packages/tools/benchmarks/dbscan_benchmark.py`), in-process run time:

| genes | dense all-pairs | sparse eps-hop |
|---|---|---|
| 1,000 | 449 ms | 209 ms |
| 5,000 | 26 s | 5.7 s |
| 10,000 | 171 s | 36 s |

**Lesson:** "Python + C-libs > subprocess" holds only if the in-process algorithm is
scalable (avoid the O(n²) all-pairs matrix). Equivalence to the binary is not bit-for-bit
(legacy BFS hop counting + custom expandCluster vs sklearn) — validate on real data before
swapping. The C++ binary's own compute time was **not** benchmarked (it couldn't be built in
this environment).

### 5.1 PhenomeMap: what was ported vs deferred

Ported (the reusable compute): edge-list encode → `biclique` binary (injectable runner) →
parse → assemble bicliques by gene-set count → subset-link scoring (gene-count ratio × KS
p-value) with transitive reduction → p-value/FDR link trim → cut-depth → unconnected-node
trim → graph of nodes/links with depth. Optional bootstrap reduction (the `bstrap` binary)
is a second injectable runner, skipped when unconfigured or on small graphs.

Deferred: the **permutation-significance** add-on (the `bicliquer` binary over an `.odemat`
matrix) is a separate statistic with a different input encoding; it can be added later as a
third injectable runner. All rendering (dot/graphml/svg/pdf/csv/json + graphviz) and the
DB label/species/publication lookups are presentation and were dropped.

## 6. Source of truth

The recovered legacy worker source lives at **`legacy/tools-worker/`** (provenance in its
README — it was built `-dirty` and existed only inside the prod image). It is the basis for
these ports.

## 7. Running the tests

```bash
# all tools tests (binary tools use injectable runners — no compiled binary needed)
cd packages/tools && uv run pytest tests/unit -q

# the scipy/sklearn-backed tools/tests need the optional extra
uv sync --all-extras   # installs the [sklearn] extra (scipy + scikit-learn)
```

## 8. Remaining work
1. Add **PhenomeMap permutation** significance (the `bicliquer` add-on) as a third injectable
   runner once the `.odemat` encoding is specified (see §5.1).
2. Decide **GeneSetViewer**'s home (UI rendering vs a pure graph-building helper).
3. Specify **TricliqueViewer**'s `.kel` / `bk-partite` contract, then port (or retire if unused).
4. Move **ABBA** into `geneweaver-db` as versioned queries.
5. Build the `TOOLBOX` binaries (`make`) in the deploy image so the binary-wrapper tools'
   default runners work in production; wire the binary paths via env vars (e.g.
   `GENEWEAVER_BICLIQUE_BINARY`, `GENEWEAVER_BSTRAP_BINARY`, `GENEWEAVER_MSET_BINARY`).
6. Validate ported tools' outputs against the legacy worker on real gene sets (esp. the
   bug-fixed HyperGeometric, the DBSCAN variant, and the PhenomeMap graph structure).
