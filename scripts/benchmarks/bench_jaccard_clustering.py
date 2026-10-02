"""JaccardClustering: legacy hand-rolled agglomerative clustering vs. the scipy port.

Answers "is the scipy port better than the original hand-rolled clustering?" on:

  - **speed**: wall time vs. number of gene sets (the legacy is O(n^3)+ Python: each merge
    rescans all cluster pairs and their members; scipy.cluster.hierarchy is C-backed
    O(n^2 log n));
  - **equivalence**: two independent checks, because the earlier version of this script
    promised an equivalence comparison in its docstring and did not implement one -- it
    discarded both return values and only timed. The claim in TOOLS_BENCHMARKS.md was
    therefore unreproducible from this repository.

      1. *port vs legacy*, for `average`: the legacy `average_cluster` is transcribed
         verbatim below, and the merge distances it produces are compared with the port's.
      2. *port vs textbook*, for `complete`/`average`/`single`/`mcquitty`: a small
         independent implementation of each linkage rule (max / mean / min / WPGMA),
         written from the definition rather than from the legacy code, so it is not a
         second copy of the thing under test.

    `ward` is deliberately excluded: the legacy `wards_cluster` recomputes Jaccard from the
    merged gene union rather than using Lance-Williams, so it is not the textbook Ward and
    the two are not expected to agree. That is a documented divergence, not a regression.
    (complete / average / single / mcquitty=weighted)?

The legacy `complete_/average_/single_/mcquitty_cluster` functions are transcribed verbatim
(they depend only on the dissimilarity matrix + `self._gsids`).

Usage:
    uv run --extra sklearn --project packages/tools python \
        scripts/benchmarks/bench_jaccard_clustering.py
"""
# ruff: noqa: D101, D103, E741  (benchmark script; transcribed legacy code)

from __future__ import annotations

import json
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


# --- independent textbook linkage, written from the definition -------------------------


def textbook_linkage(distance, method):
    """Agglomerative clustering by the textbook rule, as a reference implementation.

    Deliberately naive and independent of both the legacy code and SciPy: merge the closest
    pair, then recompute that cluster's distance to every other by the method's rule. Used
    to check the port rather than to be fast.

    Returns the merge distances in order, which is what the comparison is on -- the labels
    attached to a merge depend on tie-breaking, the distances do not.
    """
    active = {i: [i] for i in range(len(distance))}
    current = {(i, j): distance[i][j] for i in active for j in active if i < j}
    merges = []
    while len(active) > 1:
        (left, right), best = min(current.items(), key=lambda item: (item[1], item[0]))
        merges.append(round(best, 10))
        members = active[left] + active[right]
        del active[left], active[right]
        for other in list(active):
            pairs = [distance[a][b] for a in members for b in active[other]]
            if method == "complete":
                value = max(pairs)
            elif method == "single":
                value = min(pairs)
            elif method == "average":
                value = sum(pairs) / len(pairs)
            elif method == "mcquitty":
                # WPGMA: the mean of the two *cluster* distances, not of the members.
                value = (current[_key(left, other)] + current[_key(right, other)]) / 2
            else:  # pragma: no cover - guarded by the caller
                raise ValueError(method)
            current[_key(left, other)] = value
        active[left] = members
        current = {
            key: value
            for key, value in current.items()
            if key[0] in active and key[1] in active and key[0] != right and key[1] != right
        }
    return merges


def _key(a, b):
    """Pair key with a stable order, since `current` is keyed by (low, high)."""
    return (a, b) if a < b else (b, a)


def port_merge_distances(similarity, method, ids):
    """The port's merge distances, in merge order, read off its tree."""
    output = JaccardClustering().run(
        JaccardClusteringInput(geneset_ids=ids, method=method, similarity=similarity)
    )
    distances = []

    def walk(node):
        if node.geneset_id is not None:
            return
        for child in node.children:
            walk(child)
        distances.append(round(float(node.distance), 10))

    if output.tree is not None:
        walk(output.tree)
    return sorted(distances)


def legacy_merge_distances(similarity, ids):
    """Merge distances from the verbatim legacy `average_cluster`."""
    size = len(similarity)
    dissimilarity = [[1.0 - similarity[i][j] for j in range(size)] for i in range(size)]
    roots = average_cluster(_Self(list(ids)), [row[:] for row in dissimilarity])
    distances = []

    def walk(node):
        if node is None:
            return
        walk(node.left)
        walk(node.right)
        if node.left is not None or node.right is not None:
            # `average_cluster` stores `newtree.jac = 1 - minval`, i.e. the *similarity* at
            # the merge, while the port reports the *distance*. Comparing the two directly
            # makes a correct port look wrong -- which it did, until this conversion.
            distances.append(round(1.0 - float(node.jac), 10))

    for root in roots:
        walk(root)
    return sorted(distances)


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


RESULTS = os.path.join(os.path.dirname(__file__), "results")

TEXTBOOK_METHODS = ("complete", "average", "single", "mcquitty")


def check_equivalence():
    """Both equivalence checks. Returns (rows, all_passed)."""
    rows = []
    passed = True

    print("=== EQUIVALENCE 1: port vs verbatim legacy `average_cluster` ===")
    print(f"{'genesets':>9} | {'merges':>7} | {'max abs diff':>13} | result")
    for size in (8, 12, 20, 30):
        ids = [f"GS{i}" for i in range(size)]
        similarity = make_similarity(size, seed=size)
        port = port_merge_distances(similarity, "average", ids)
        legacy = legacy_merge_distances(similarity, ids)
        if len(port) != len(legacy):
            worst, ok = float("nan"), False
        else:
            worst = max((abs(a - b) for a, b in zip(port, legacy, strict=True)), default=0.0)
            ok = worst < 1e-9
        passed &= ok
        rows.append(
            {
                "check": "legacy",
                "method": "average",
                "genesets": size,
                "merges": len(port),
                "max_abs_diff": worst,
                "passed": bool(ok),
            }
        )
        print(f"{size:>9} | {len(port):>7} | {worst:>13.2e} | {'MATCH' if ok else 'DIFFERS'}")

    print("\n=== EQUIVALENCE 2: port vs independent textbook linkage ===")
    print(f"{'method':>10} | {'genesets':>9} | {'max abs diff':>13} | result")
    for method in TEXTBOOK_METHODS:
        for size in (8, 12, 20):
            ids = [f"GS{i}" for i in range(size)]
            similarity = make_similarity(size, seed=size + len(method))
            distance = [[1.0 - similarity[i][j] for j in range(size)] for i in range(size)]
            port = port_merge_distances(similarity, method, ids)
            reference = sorted(textbook_linkage(distance, method))
            if len(port) != len(reference):
                worst, ok = float("nan"), False
            else:
                worst = max(
                    (abs(a - b) for a, b in zip(port, reference, strict=True)), default=0.0
                )
                ok = worst < 1e-9
            passed &= ok
            rows.append(
                {
                    "check": "textbook",
                    "method": method,
                    "genesets": size,
                    "merges": len(port),
                    "max_abs_diff": worst,
                    "passed": bool(ok),
                }
            )
            print(f"{method:>10} | {size:>9} | {worst:>13.2e} | {'MATCH' if ok else 'DIFFERS'}")

    print("\n  `ward` excluded by design: the legacy recomputes Jaccard from the merged")
    print("  gene union rather than using Lance-Williams, so it is not textbook Ward.")
    return rows, passed


def measure_speed():
    """Wall time, legacy vs port, for method=average."""
    print("\n=== SPEED: legacy hand-rolled vs scipy port (method=average) ===")
    header = f"{'genesets':>8} | {'legacy(ms)':>11} | {'scipy(ms)':>10} | {'speedup':>9}"
    print(header)
    print("-" * len(header))
    rows = []
    for size in (10, 25, 50, 100, 150, 200):
        similarity = make_similarity(size)
        ids = [f"GS{i}" for i in range(size)]
        dissimilarity = [[1.0 - similarity[i][j] for j in range(size)] for i in range(size)]

        start = time.perf_counter()
        average_cluster(_Self(ids), [row[:] for row in dissimilarity])
        legacy_ms = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        JaccardClustering().run(
            JaccardClusteringInput(geneset_ids=ids, method="average", similarity=similarity)
        )
        port_ms = (time.perf_counter() - start) * 1000

        speedup = legacy_ms / port_ms if port_ms else float("inf")
        rows.append(
            {
                "genesets": size,
                "legacy_ms": round(legacy_ms, 2),
                "port_ms": round(port_ms, 2),
                "speedup": round(speedup, 2),
            }
        )
        print(f"{size:>8} | {legacy_ms:>11.1f} | {port_ms:>10.1f} | {speedup:>8.1f}x")
    return rows


def main():
    equivalence, passed = check_equivalence()
    speed = measure_speed()

    # Written out so `plot_benchmarks.py` draws the measurements rather than literals
    # transcribed by hand -- the charts could previously disagree with reality silently.
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, "jaccard_clustering.json")
    with open(path, "w") as handle:
        json.dump({"equivalence": equivalence, "speed": speed}, handle, indent=2)
    print(f"\nwrote {path}")

    if not passed:
        print("\nEQUIVALENCE FAILED -- the port does not reproduce the reference")
        return 1
    print("\nequivalence: all checks match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
