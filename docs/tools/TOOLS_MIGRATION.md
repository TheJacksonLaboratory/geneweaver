# GeneWeaver Tools — Migration & Reimplementation

> **Scope:** migrate the legacy GeneWeaver analysis tools onto the modern
> `geneweaver-tools` `AbstractTool` framework (`packages/tools`), as faithful, pure,
> testable reimplementations — decoupled from the legacy DB/Celery/file plumbing.
>
> **Status:** 9 compute tools ported; 2 moved to the DB layer (SimilarGenesets, ABBA);
> 2 flagged (presentation / incomplete). **`packages/tools` unit suite: 75 passing;
> `packages/db` suite green (incl. 10 new ABBA tests).** ABBA, PhenomeMap, HyperGeometric,
> and DBSCAN validated against the legacy tools on the local DB (see §9); the algorithm
> changes are benchmarked in [TOOLS_BENCHMARKS.md](TOOLS_BENCHMARKS.md).
> **Last updated:** 2026-06-10

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
| DBSCAN | `dbscan` | in-process (default) + binary wrapper | the default `DBSCAN` is the in-process scipy+sklearn impl (`[sklearn]`), validated identical to the binary and far faster (see [TOOLS_BENCHMARKS.md](TOOLS_BENCHMARKS.md) §1). `BinaryDBSCAN` keeps the C++ binary path (encode bipartite graph → `dbscan` binary → decode JSON clusters; no extra required). |
| UpSet | `upset` | pure | intersection sizes per exact gene-set combination (legacy `os.system` calls were commented out) |
| MSET | `mset` | binary wrapper | wraps `MSETcpp` (Monte-Carlo enrichment); injectable runner. **Bug fix**: legacy used `group_1_background` for both lists. |
| PhenomeMap | `phenome_map` | binary wrapper (+ pure pipeline) | maximal-biclique intersection graph. `build_edge_list`/`parse_bicliques` (pure) wrap the `biclique` C binary via an injectable runner; the subset-link + scoring pass, p-value/FDR trim, cut-depth, and unconnected-node trim are pure; optional bootstrap reduction via a second injectable runner. KS term is a pure-Python transcription of the legacy asymptotic KS (a `scipy.stats.ks_2samp` swap was reverted — [TOOLS_BENCHMARKS.md](TOOLS_BENCHMARKS.md) §4). All rendering (dot/graphml/svg/pdf/csv/json, graphviz) dropped; permutation add-on (`bicliquer`) deferred — see §5.1. |

### Moved to the data layer (not an `AbstractTool`)

| Legacy tool | Where it went | Why |
|---|---|---|
| SimilarGenesets | `geneweaver-db`: `geneset_jaccard.calculate_jaccard()` + `query/geneset_jaccard.py` | No in-process algorithm — it triggers the `calculate_jaccard` Postgres stored proc + timestamp/cache bookkeeping (one set vs all ~50k, over 2M+ memberships). Ported the stored proc to a versioned, testable query; heavy set-work stays in Postgres. A pure-Python port would be a perf/memory regression. |
| ABBA | `geneweaver-db`: `abba.abba()` + `query/abba.py` | DB query/aggregation: builds 4 session temp tables (input genes → homology-expanded genes of interest → matching gene sets → recurring result genes) plus tier/species count rollups. Ported to versioned, parameterised query builders + an orchestration function returning an `ABBAResult`. **Improvements**: list values bind via `= ANY(%(...)s)` and temp-table names use `sql.Identifier` (the legacy string-joined `IN (...)` clauses were an injection/quoting hazard); the "ignore homology" branch now actually creates its temp table (legacy ran a bare `SELECT` and broke every later step); per-call uuid table suffixes for concurrency. Rendering (JSON dump, zero-padding/list reshaping) dropped. |

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
- **PhenomeMap** — the whole graph pipeline (subset links, transitive reduction,
  p-value/FDR trim, cut/trim) is pure and unit-tested with an injectable biclique runner —
  no compiled binary needed for tests. The empty-FDR case that crashes the legacy tool
  (`p_values` empty → divide-by-zero) is guarded. The KS term of the link score is a
  pure-Python transcription of the legacy asymptotic KS (`ks_2samp_pvalue`); an earlier
  `scipy.stats.ks_2samp` swap was **reverted** after benchmarking showed scipy was slower
  *and* numerically different (exact vs. the legacy asymptotic — see
  [TOOLS_BENCHMARKS.md](TOOLS_BENCHMARKS.md) §4).
  **Bug fixed during validation (§9):** after a level is cut, the port no longer emits
  dangling child/parent links to trimmed nodes (the legacy tool filtered these only at
  render time, so the port leaked them into its graph output).
- **DBSCAN** — the in-process scipy+sklearn implementation is now the **default** `DBSCAN`
  (the compiled-binary wrapper is `BinaryDBSCAN`); benchmarked identical to the binary and
  4.9×–56× faster (§5, [TOOLS_BENCHMARKS.md](TOOLS_BENCHMARKS.md) §1).
  **Bug fixed during validation (§9):** `DBSCANInput.epsilon` was typed `float`, so a caller
  passing `epsilon=1` produced `"1.0"`, which the binary's integer `atol` rejects ("Epsilon
  is invalid"). Epsilon is an integer hop-radius for this binary, so it is now typed `int`.
  (The unit tests used fake runners with `epsilon=0.5` and never exercised the real binary.)
- **ABBA** — replaced the legacy string-joined `IN (...)` clauses with parameterised
  `= ANY(%(...)s)` binds and `sql.Identifier` temp-table names (fixes the SQL-injection /
  quoting hazard); fixed the "ignore homology" branch that ran a bare `SELECT` and never
  created the genes-of-interest table (breaking every later step); per-call uuid table
  suffixes for concurrency safety.
- **dead/conflicted code** — excluded the unparseable `jaccardsimilarityblueprint2.py`
  (merge-conflict marker) from lint; dropped vendored/compiled artifacts from version control.

## 5. DBSCAN: subprocess binary vs. in-process (C-libs)

The default in-process `DBSCAN` (`dbscan/sklearn_tool.py`, `[sklearn]` extra; the legacy
binary path is `BinaryDBSCAN`) reproduces the legacy graph DBSCAN (gene co-membership graph +
BFS hop radius) in-process: a **sparse eps-hop neighbour graph** (bounded sparse matrix
powers) → `sklearn.cluster.DBSCAN(metric="precomputed")`. No
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
4. Build the `TOOLBOX` binaries (`make`) in the deploy image so the binary-wrapper tools'
   default runners work in production; wire the binary paths via env vars (e.g.
   `GENEWEAVER_BICLIQUE_BINARY`, `GENEWEAVER_BSTRAP_BINARY`, `GENEWEAVER_MSET_BINARY`).
5. Validate the remaining ported tools against the legacy worker on real gene sets. ABBA,
   PhenomeMap, HyperGeometric, and DBSCAN done — see §9.
6. **Drop MSET's static background files — resolve the background from the DB.** The legacy
   MSET ships ~301 precomputed `TOOLBOX/CS_Mset/backgroundFiles/*BG.txt` files (per species ×
   gene-db / attribution), generated by `createBackgrounds.py`. These are a *denormalized cache
   of DB data* and go **stale whenever the gene data is reloaded** — MSETcpp requires each input
   list to be a strict subset of its background, so a stale background fails with
   `list_2 not subset of its background` (this is exactly GWC-45 on dev after the Dec-2025 gene
   reload; the legacy stopgap is to regenerate the files per-environment onto the results volume —
   see `MSET.py` `GW_MSET_BG_DIR`). When porting MSET to `packages/tools`, the background should be
   **resolved from the DB at run time** (the same query `createBackgrounds.py` uses) and passed via
   `ToolInput` — the caller owns DB access, exactly like the two input gene lists — so the universe
   is always the same vintage as the genes. This eliminates the static files, the regeneration job,
   the per-env storage, and the whole class of staleness bugs. (Also fold in the createBackgrounds
   py3 fixes: text-mode writes and the correct DB port.)

   **Also fix the universe definition, not just its freshness.** `createBackgrounds.py` builds the
   universe only from *curated* genesets (`cur_id NOT IN (4,5)`), so a gene that appears **only** in
   a Tier-IV/V set is absent from the background even when the file is perfectly fresh. A large
   Tier-IV DEG set can then contain real genes (e.g. lncRNAs / antisense unique to that set) that
   are "outside" its own universe, and MSETcpp rejects the whole list with
   `list_2 not subset of its background` (observed on dev for GS 407805 — 131 of 9,623 genes, all
   real human genes present in no other geneset). This is **not** staleness and not a monorepo
   regression (the same logic runs in sqa/prod). The correct V3 universe is the **full gene space**
   for the id-type/species (all such genes GeneWeaver knows, from `extsrc.gene`), not "genes that
   happen to appear in curated genesets" — then any real gene is in-universe by construction. Until
   then, MSET fails early with a clear message naming the out-of-universe genes (see
   `MSET.check_list_in_background`) instead of surfacing the raw C++ stderr.

## 9. Validation against the legacy tools (local DB)

ABBA, PhenomeMap, HyperGeometric, and DBSCAN were validated against faithful transcriptions
of the legacy logic, run on the seeded local Postgres (`gw-local-pg`, 50k gene sets / 2M+
memberships). Harness: `scripts/validation/` (`validate_abba.py`, `validate_phenomemap.py`,
`validate_hypergeometric.py`, `validate_dbscan.py`, `_legacy_phenomemap.py`).

**ABBA** — the port and a verbatim transcription of the legacy SQL pipeline (homology-on
path) run against the same DB produce identical results: `available_genes`,
`available_genesets`, genes of interest (58), matching gene sets (top 50), and result genes
(top 50) all match for gene set 514's symbols over all species / tiers 1-5.
(`extsrc.homology` is empty locally, so homology expansion is a no-op — the aggregation,
group-access gate, auto min-genes gate, and tier/species filters are what's exercised.)

**PhenomeMap** — both the port and the legacy in-memory algorithm consume the *same*
`biclique` binary output, so validation isolates the ported Python pipeline. On a real
17-gene-set / 166-gene graph (18 enumerated bicliques) across 6 parameter combinations
(no-trim, p-value, p-value+FDR, min_genes, two cut-depth cases), the node sets, link sets,
link scores (**max diff 0.0**), and cut depths all match. *Note:* every gene in the local DB
has `gene_rank = 0.0`, so the KS term is 1.0 for every link (link scores reduce to the
gene-count ratio) — the KS comparison here is vacuous. A separate benchmark
([TOOLS_BENCHMARKS.md](TOOLS_BENCHMARKS.md) §4) exercises the KS on non-degenerate ranks and
drove the revert from `scipy` back to the faithful legacy KS.

**HyperGeometric** — validated against a verbatim transcription of the legacy `fisher()`
*and* an independent `scipy` oracle over 45 gene-set pairs (112-gene universe). The odds
ratio matches the legacy exactly (45/45); the upper tail matches the legacy `ut` — the one
tail computed before the accumulation bug pollutes it (45/45, max diff 2e-16); the port's
two-tailed matches `scipy.stats.fisher_exact` (45/45, max diff 1e-16) and its upper/lower
match an independent `scipy.stats.hypergeom` pmf oracle using the same tail definition
(45/45). The legacy two-tailed is **wrong in 35/45 pairs** (the `pval` accumulation bug the
port fixes) — so the port matches the legacy where the legacy is correct and matches the
oracle where the legacy is not.

**DBSCAN** — both the port and the legacy invoke the *same* `dbscan` C++ binary, so
validation covers the port's encode/gate/decode. The bipartite input string is
**byte-identical** to a verbatim transcription of the legacy encoding; across 6
(epsilon, min_points) settings on a real 9-gene-set / 70-gene graph, the `ran` gate, gene/
gene-set counts, and decoded clusters all match (including a not-run case).

Notes:
- The recovered `biclique` binary uses POSIX `hsearch` for label storage, which prints empty
  labels on macOS. The validation rebuilds it with the equivalent linear-search label code
  (the block already present, commented, in `bigraph.c`); the committed source is untouched.
- The `dbscan` C++ binary builds on macOS via `xcrun clang++ -stdlib=libc++ -isysroot $SDK
  -isystem $SDK/usr/include/c++/v1` (the makefile's bare `g++` can't find `<iostream>`).
- Where the local DB container's host port mapping is unavailable, the gene-set graphs are
  dumped via `docker exec ... psql` to a JSON fixture (`GENEWEAVER_*_GRAPH_JSON`); it is the
  same data the in-script DB query returns.
- **Bugs found & fixed:** (PhenomeMap) the cut-depth cases initially produced dangling
  child/parent links in the port's output (links to nodes removed by the cut); the legacy
  tool filtered these only at render time, the port now filters them when building the graph
  (covered by `test_cut_does_not_leave_dangling_links`). (DBSCAN) `epsilon` was typed
  `float`, breaking the binary's integer parser — now `int` (see §4).
