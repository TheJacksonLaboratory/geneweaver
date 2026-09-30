"""Robust summary of how far p-values move, for the pairs where they move at all."""

import json
import math
import os
import pathlib
import statistics

from scipy.stats import hypergeom

OUT = pathlib.Path(os.environ.get("MSET_IMPACT_DIR", "/tmp/mset-impact"))
pairs = json.loads((OUT / "pairs.json").read_text())
U = {"1": (32356, 66866, "Mus musculus"), "2": (30711, 40956, "Homo sapiens")}
for sp, (N_old, N_new, name) in U.items():
    moved = []
    for pr in pairs[sp]:
        K, n, k = pr["K"], pr["n"], pr["k"]
        if k == 0:
            continue  # p = 1 under both; no overlap to be significant about
        po = float(hypergeom.sf(k - 1, N_old, K, n))
        pn = float(hypergeom.sf(k - 1, N_new, K, n))
        if po > 0 and pn > 0 and abs(po - pn) > 1e-12:
            moved.append((po, pn))
    print(f"=== {name}: universe {N_old:,} -> {N_new:,}")
    print(
        f"  pairs with a non-zero overlap        {sum(1 for p in pairs[sp] if p['k'] > 0)}/{len(pairs[sp])}"
    )
    print(f"  pairs whose p-value actually moves   {len(moved)}")
    if moved:
        # log10 shift is the stable way to describe this: the raw ratio explodes in the tail.
        d = sorted(math.log10(po / pn) for po, pn in moved)
        print(
            f"  shift in -log10(p):  median {statistics.median(d):.2f}  "
            f"p90 {d[int(0.9 * len(d)) - 1]:.2f}  max {d[-1]:.1f}"
        )
        print(
            f"  i.e. p typically divided by ~{10 ** statistics.median(d):.1f}x "
            f"(p90 ~{10 ** d[int(0.9 * len(d)) - 1]:.0f}x)"
        )
        near = [(po, pn) for po, pn in moved if 0.001 < po < 0.5]
        print(f"  pairs near the decision boundary (0.001<p_old<0.5): {len(near)}")
        if near:
            dn = sorted(math.log10(po / pn) for po, pn in near)
            print(f"    their median shift: p divided by {10 ** statistics.median(dn):.2f}x")
    print()
