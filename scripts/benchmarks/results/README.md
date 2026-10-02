# Benchmark measurements

Committed on purpose. `plot_benchmarks.py` draws the charts in `docs/tools/img/` from these
files, and `docs/tools/TOOLS_BENCHMARKS.md` quotes them, so keeping them in the repository
is what makes those figures traceable to a run rather than to someone's notes. Before this,
both the tables and the charts held hand-copied literals, and one headline figure had
stopped being reproducible without anything saying so.

Regenerate with the commands in TOOLS_BENCHMARKS.md ("How to reproduce"). Each benchmark
overwrites its own file.

## Provenance of the committed set

| | |
|---|---|
| measured | 2026-10-02 |
| host | macOS / Apple silicon, Python 3.12 (pure-compute benchmarks) |
| DBSCAN | Linux `python:3.12-slim` container, TOOLBOX `dbscan` built from source |

DBSCAN is measured on Linux deliberately: the binary's input limit is
`MAX_ARG_STRLEN` (128 KiB per argv entry), which is platform-specific and is what makes the
binary fail above ~1,000 genes. Measuring it on the platform the native worker actually runs
is the only result worth quoting.

Timings are wall-clock on a developer machine, so treat the *ratios* as the finding and the
absolute milliseconds as indicative. The equivalence checks are exact and
machine-independent; `bench_jaccard_clustering.py` exits non-zero if they stop matching.
