"""Render the benchmark plots embedded in docs/tools/TOOLS_BENCHMARKS.md.

The data below is the measured output of the four scripts in scripts/benchmarks/ run
against the seeded local Postgres (`gw-local-pg`, host 127.0.0.1:5433) + the locally-built
`dbscan`/`biclique` binaries. Re-run the benchmarks, paste the new numbers here, and run:

    uv run --with matplotlib --extra sklearn --project packages/tools \
        python scripts/benchmarks/plot_benchmarks.py

PNGs are written to docs/tools/img/.
"""
# ruff: noqa: D103  (plotting script)

from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "tools", "img")
RESULTS = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(OUT, exist_ok=True)


def load(name):
    """Read a benchmark's measurements.

    Every series below used to be a literal list copied by hand out of a benchmark run.
    That cannot be checked and cannot go stale visibly: the chart and the table in
    TOOLS_BENCHMARKS.md could disagree with what the code now does and nothing would say
    so. The benchmarks write JSON into `results/`; this reads it.

    :raises SystemExit: If the measurements are missing, naming the script to run. Drawing
        a chart from no data would be worse than not drawing one.
    """
    path = os.path.join(RESULTS, f"{name}.json")
    if not os.path.exists(path):
        raise SystemExit(
            f"missing {path} -- run scripts/benchmarks/bench_{name}.py first "
            "(DBSCAN additionally needs GENEWEAVER_DBSCAN_BINARY)"
        )
    with open(path) as handle:
        return json.load(handle)


plt.rcParams.update({"figure.dpi": 130, "font.size": 10, "axes.grid": True, "grid.alpha": 0.3})

PORT = "#1b7837"  # green  - the Python port / in-process impl
LEG = "#762a83"  # purple - the legacy / binary baseline


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {os.path.relpath(path)}")


# --- 1. DBSCAN: in-process sklearn vs the C++ binary -------------------------------------
def plot_dbscan():
    rows = [row for row in load("dbscan")["speed"] if row["binary_ms"] is not None]
    genes = [row["genes"] for row in rows]
    binary = [row["binary_ms"] for row in rows]
    sklearn = [row["sklearn_ms"] for row in rows]
    speedup = [row["speedup"] for row in rows]

    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(genes, binary, "o-", color=LEG, label="C++ binary (subprocess)")
    ax.plot(genes, sklearn, "o-", color=PORT, label="in-process scipy+sklearn")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("distinct genes in the graph")
    ax.set_ylabel("end-to-end wall time (ms, log scale)")
    ax.set_title("DBSCAN — in-process port vs C++ binary (eps=2, minPts=3)")
    for x, b, s, sp in zip(genes, binary, sklearn, speedup):
        ax.annotate(
            f"{sp:.0f}×",
            (x, s),
            textcoords="offset points",
            xytext=(0, -14),
            ha="center",
            fontsize=8,
            color=PORT,
        )
    ax.legend()
    save(fig, "dbscan_speed.png")


# --- 2. JaccardClustering: scipy linkage vs hand-rolled agglomerative --------------------
def plot_jaccard():
    rows = load("jaccard_clustering")["speed"]
    n = [row["genesets"] for row in rows]
    legacy = [row["legacy_ms"] for row in rows]
    scipy = [row["port_ms"] for row in rows]

    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(n, legacy, "o-", color=LEG, label="legacy hand-rolled (Python)")
    ax.plot(n, scipy, "o-", color=PORT, label="scipy.cluster.hierarchy port")
    ax.set_yscale("log")
    ax.set_xlabel("number of gene sets")
    ax.set_ylabel("wall time (ms, log scale)")
    ax.set_title("JaccardClustering — scipy linkage vs hand-rolled (method=average)")
    # speedup callouts for the meaningful (warmed-up) sizes
    for x, le, sc in zip(n, legacy, scipy):
        if x >= 50:
            ax.annotate(
                f"{le / sc:.0f}×",
                (x, le),
                textcoords="offset points",
                xytext=(0, 6),
                ha="center",
                fontsize=8,
                color=PORT,
            )
    ax.legend()
    save(fig, "jaccard_speed.png")


# --- 3. HyperGeometric: math.comb port vs legacy combtl-float ----------------------------
def plot_hypergeometric():
    rows = load("hypergeometric")["speed"]
    universe = [row["universe"] for row in rows]
    legacy = [row["legacy_ms"] for row in rows]
    port = [row["port_ms"] for row in rows]
    ratio = [row["ratio"] for row in rows]

    x = range(len(universe))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.bar([i - w / 2 for i in x], legacy, w, color=LEG, label="legacy combtl (float)")
    ax.bar([i + w / 2 for i in x], port, w, color=PORT, label="port math.comb (exact int)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(universe)
    ax.set_xlabel("universe size (contingency-table total)")
    ax.set_ylabel("wall time (ms, 200 tables)")
    ax.set_title("HyperGeometric — exact math.comb vs legacy combtl  (port also fixes a bug)")
    for i, (le, r) in enumerate(zip(legacy, ratio)):
        ax.annotate(
            f"{r:.1f}×",
            (i, le),
            textcoords="offset points",
            xytext=(0, 4),
            ha="center",
            fontsize=8,
            color=PORT,
        )
    ax.legend()
    save(fig, "hypergeometric_speed.png")


# --- 4. PhenomeMap KS: legacy asymptotic KS vs scipy.stats.ks_2samp (reverted) -----------
def plot_phenomemap_ks():
    rows = load("phenomemap_ks")["speed"]
    n = [row["n"] for row in rows]
    legacy = [row["legacy_ms"] for row in rows]
    scipy = [row["scipy_ms"] for row in rows]
    dp = [row["max_abs_dp"] for row in rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2))
    x = range(len(n))
    w = 0.38
    ax1.bar([i - w / 2 for i in x], legacy, w, color=PORT, label="legacy asymptotic KS (kept)")
    ax1.bar([i + w / 2 for i in x], scipy, w, color=LEG, label="scipy.stats.ks_2samp")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(n)
    ax1.set_xlabel("sample size n")
    ax1.set_ylabel("wall time (ms, 2000 calls)")
    ax1.set_title("Runtime — scipy is slower")
    ax1.legend()

    ax2.plot(n, dp, "o-", color="#b35806")
    ax2.set_xscale("log")
    ax2.set_xlabel("sample size n (log scale)")
    ax2.set_ylabel(r"max $|\Delta p|$ vs legacy")
    ax2.set_title("Divergence — scipy changes the p-value")
    ax2.axhline(0, color="gray", lw=0.6)

    fig.suptitle("PhenomeMap KS term — why the scipy swap was reverted", y=1.02)
    save(fig, "phenomemap_ks.png")


# --- 5. Verdict summary: speedup of the port across tools --------------------------------
def plot_summary():
    # Largest size at which the comparison is actually possible, per tool. For DBSCAN that
    # is the largest graph the *binary* can still process: past it the binary fails with
    # E2BIG rather than running slowly, so there is no ratio to report.
    dbscan = [row for row in load("dbscan")["speed"] if row["speedup"] is not None]
    jaccard = load("jaccard_clustering")["speed"][-1]
    hyper = load("hypergeometric")["speed"][0]
    ks = [row for row in load("phenomemap_ks")["speed"] if row["n"] == 200][0]

    labels = [
        f"DBSCAN\n({dbscan[-1]['genes']} genes)",
        f"JaccardClustering\n({jaccard['genesets']} sets)",
        f"HyperGeometric\n(universe {hyper['universe']})",
        f"PhenomeMap KS\n(n={ks['n']})",
    ]
    speedups = [
        dbscan[-1]["speedup"],
        jaccard["speedup"],
        hyper["ratio"],
        ks["legacy_ms"] / ks["scipy_ms"],
    ]
    colors = [PORT, PORT, PORT, LEG]

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    bars = ax.bar(labels, speedups, color=colors)
    ax.axhline(1.0, color="gray", lw=1, ls="--")
    ax.set_yscale("log")
    ax.set_ylabel("speedup of Python impl  (×, log scale)")
    ax.set_title("Port vs legacy — speedup by tool  (>1 = Python faster)")
    for bar, sp in zip(bars, speedups):
        ax.annotate(
            f"{sp:.2f}×" if sp < 10 else f"{sp:.0f}×",
            (bar.get_x() + bar.get_width() / 2, sp),
            textcoords="offset points",
            xytext=(0, 4),
            ha="center",
            fontsize=9,
        )
    ax.annotate(
        "scipy SLOWER → reverted",
        xy=(3, speedups[3]),
        xytext=(3, 0.62),
        ha="center",
        fontsize=8,
        color=LEG,
        arrowprops={"arrowstyle": "->", "color": LEG, "lw": 0.8},
    )
    save(fig, "speedup_summary.png")


def main():
    plot_dbscan()
    plot_jaccard()
    plot_hypergeometric()
    plot_phenomemap_ks()
    plot_summary()


if __name__ == "__main__":
    main()
