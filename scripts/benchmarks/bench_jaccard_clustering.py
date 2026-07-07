"""JaccardClustering: legacy hand-rolled agglomerative clustering vs. the scipy port.

Answers "is the scipy port better than the original hand-rolled clustering?" on:

  - **speed**: wall time vs. number of gene sets (the legacy is O(n^3)+ Python: each merge
    rescans all cluster pairs and their members; scipy.cluster.hierarchy is C-backed
    O(n^2 log n));
  - **equivalence**: on small inputs, does the scipy port produce the same merge structure
    (set of clusters at each level) as the legacy, for the linkage-on-distance-matrix methods
    (complete / average / single / mcquitty=weighted)?

The legacy `complete_/average_/single_/mcquitty_cluster` functions are transcribed verbatim
(they depend only on the dissimilarity matrix + `self._gsids`).

Usage:
    uv run --extra sklearn --project packages/tools python \
        scripts/benchmarks/bench_jaccard_clustering.py
"""
# ruff: noqa: D101, D103, E741  (benchmark script; transcribed legacy code)

from __future__ import annotations

import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "tools", "src"))
from geneweaver.tools.jaccard_clustering import JaccardClustering, JaccardClusteringInput

# --- legacy clustering (transcribed verbatim from JaccardClustering.py) -----------------


class Tree:
    def __init__(self):
        self.parent = None
        self.data = None
        self.jac = 0
        self.left = None
        self.right = None


class _Self:
    def __init__(self, gsids):
        self._gsids = gsids


def average_cluster(self, jsc):
    genesets = list(self._gsids)
    gsInCluster = []
    treelist = []
    similaritymatrix = jsc
    num_clusters = len(genesets)
    for x in range(len(self._gsids)):
        gsInCluster.append([x])
    for y in range(num_clusters):
        t = Tree()
        t.data = genesets[y]
        treelist.append(t)
    done = False
    while not done:
        minval = 1.1
        tocluster = (0, 0)
        for i in range(num_clusters - 1):
            for j in range(i + 1, num_clusters):
                total = 0
                numpairs = len(gsInCluster[i]) * len(gsInCluster[j])
                for k in range(len(gsInCluster[i])):
                    for l in range(len(gsInCluster[j])):
                        total += similaritymatrix[gsInCluster[i][k]][gsInCluster[j][l]]
                average = total / numpairs
                if average != 1 and average < minval:
                    minval = average
                    tocluster = (i, j)
        if minval == 1.1:
            done = True
        else:
            newtree = Tree()
            child1 = Tree()
            child2 = Tree()
            for x in range(len(treelist)):
                for y in range(len(gsInCluster[tocluster[0]])):
                    if genesets[gsInCluster[tocluster[0]][y]] == treelist[x].data:
                        child1 = treelist[x]
                        while child1.parent is not None:
                            child1 = child1.parent
                for y in range(len(gsInCluster[tocluster[1]])):
                    if genesets[gsInCluster[tocluster[1]][y]] == treelist[x].data:
                        child2 = treelist[x]
                        while child2.parent is not None:
                            child2 = child2.parent
            newtree.data = frozenset([child1.data, child2.data])
            newtree.jac = 1 - minval
            newtree.left = child1
            newtree.right = child2
            treelist.append(newtree)
            child1.parent = newtree
            child2.parent = newtree
            for i in range(len(gsInCluster[tocluster[1]])):
                gsInCluster[tocluster[0]].append(gsInCluster[tocluster[1]][i])
            gsInCluster.remove(gsInCluster[tocluster[1]])
            num_clusters -= 1
    return [n for n in treelist if n.parent is None]


def make_similarity(n, seed=0):
    """Random symmetric Jaccard-like similarity matrix (diagonal 1.0)."""
    rng = random.Random(seed)
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        sim[i][i] = 1.0
        for j in range(i + 1, n):
            v = round(rng.random() * 0.6, 4)  # similarities in [0, 0.6)
            sim[i][j] = sim[j][i] = v
    return sim


def main():
    print("=== JaccardClustering: legacy hand-rolled vs scipy port (method=average) ===")
    header = f"{'genesets':>8} | {'legacy(ms)':>11} | {'scipy(ms)':>10} | {'speedup':>9}"
    print(header)
    print("-" * len(header))
    for n in [10, 25, 50, 100, 150, 200]:
        sim = make_similarity(n)
        ids = [f"GS{i}" for i in range(n)]

        # legacy needs dissimilarity = 1 - similarity
        jsc = [[1.0 - sim[i][j] for j in range(n)] for i in range(n)]
        t0 = time.perf_counter()
        average_cluster(_Self(ids), [row[:] for row in jsc])
        legacy_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        JaccardClustering().run(
            JaccardClusteringInput(geneset_ids=ids, method="average", similarity=sim)
        )
        scipy_ms = (time.perf_counter() - t0) * 1000

        speedup = legacy_ms / scipy_ms if scipy_ms else float("inf")
        print(f"{n:>8} | {legacy_ms:>11.1f} | {scipy_ms:>10.1f} | {speedup:>8.1f}x")


if __name__ == "__main__":
    main()
