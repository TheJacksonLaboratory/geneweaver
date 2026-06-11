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

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "tools", "img")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({"figure.dpi": 130, "font.size": 10, "axes.grid": True, "grid.alpha": 0.3})

PORT = "#1b7837"   # green  - the Python port / in-process impl
LEG = "#762a83"    # purple - the legacy / binary baseline


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {os.path.relpath(path)}")


# --- 1. DBSCAN: in-process sklearn vs the C++ binary -------------------------------------
def plot_dbscan():
    genes = [100, 500, 1000, 2000, 5000]
    binary = [17.2, 540.4, 3634.4, 26774.3, 358390.8]
    sklearn = [5.0, 45.9, 212.9, 955.6, 5877.2]
    speedup = [b / s for b, s in zip(binary, sklearn)]

    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(genes, binary, "o-", color=LEG, label="C++ binary (subprocess)")
    ax.plot(genes, sklearn, "o-", color=PORT, label="in-process scipy+sklearn")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("distinct genes in the graph")
    ax.set_ylabel("end-to-end wall time (ms, log scale)")
    ax.set_title("DBSCAN — in-process port vs C++ binary (eps=2, minPts=3)")
    for x, b, s, sp in zip(genes, binary, sklearn, speedup):
        ax.annotate(f"{sp:.0f}×", (x, s), textcoords="offset points", xytext=(0, -14),
                    ha="center", fontsize=8, color=PORT)
    ax.legend()
    save(fig, "dbscan_speed.png")


# --- 2. JaccardClustering: scipy linkage vs hand-rolled agglomerative --------------------
def plot_jaccard():
    n = [10, 25, 50, 100, 150, 200]
    legacy = [0.1, 1.1, 7.6, 57.9, 189.3, 446.2]
    scipy = [2.5, 0.4, 0.8, 1.6, 2.2, 4.3]

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
            ax.annotate(f"{le / sc:.0f}×", (x, le), textcoords="offset points",
                        xytext=(0, 6), ha="center", fontsize=8, color=PORT)
    ax.legend()
    save(fig, "jaccard_speed.png")


# --- 3. HyperGeometric: math.comb port vs legacy combtl-float ----------------------------
def plot_hypergeometric():
    universe = [50, 100, 200, 400, 800]
    legacy = [3.5, 8.6, 26.1, 103.2, 403.7]
    port = [1.2, 3.0, 10.4, 54.4, 354.9]
    ratio = [le / p for le, p in zip(legacy, port)]

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
        ax.annotate(f"{r:.1f}×", (i, le), textcoords="offset points", xytext=(0, 4),
                    ha="center", fontsize=8, color=PORT)
    ax.legend()
    save(fig, "hypergeometric_speed.png")


# --- 4. PhenomeMap KS: legacy asymptotic KS vs scipy.stats.ks_2samp (reverted) -----------
def plot_phenomemap_ks():
    n = [10, 50, 200, 1000]
    legacy = [23.6, 45.3, 149.3, 1167.5]
    scipy = [258.4, 287.0, 429.1, 1517.5]
    dp = [1.12e-01, 4.10e-02, 1.81e-02, 3.33e-02]

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
    labels = ["DBSCAN\n(5k genes)", "JaccardClustering\n(200 sets)",
              "HyperGeometric\n(universe 50)", "PhenomeMap KS\n(n=200)"]
    speedups = [60.98, 104.5, 2.92, 149.3 / 429.1]
    colors = [PORT, PORT, PORT, LEG]

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    bars = ax.bar(labels, speedups, color=colors)
    ax.axhline(1.0, color="gray", lw=1, ls="--")
    ax.set_yscale("log")
    ax.set_ylabel("speedup of Python impl  (×, log scale)")
    ax.set_title("Port vs legacy — speedup by tool  (>1 = Python faster)")
    for bar, sp in zip(bars, speedups):
        ax.annotate(f"{sp:.2f}×" if sp < 10 else f"{sp:.0f}×",
                    (bar.get_x() + bar.get_width() / 2, sp),
                    textcoords="offset points", xytext=(0, 4), ha="center", fontsize=9)
    ax.annotate("scipy SLOWER → reverted", xy=(3, speedups[3]),
                xytext=(3, 0.62), ha="center", fontsize=8, color=LEG,
                arrowprops={"arrowstyle": "->", "color": LEG, "lw": 0.8})
    save(fig, "speedup_summary.png")


def main():
    plot_dbscan()
    plot_jaccard()
    plot_hypergeometric()
    plot_phenomemap_ks()
    plot_summary()


if __name__ == "__main__":
    main()
