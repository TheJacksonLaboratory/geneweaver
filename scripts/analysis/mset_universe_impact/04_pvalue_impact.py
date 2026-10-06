"""p-value impact of the MSET universe rule change, on real dev gene-set pairs."""

import json
import os
import pathlib
import statistics

from scipy.stats import hypergeom

OUT = pathlib.Path(os.environ.get("MSET_IMPACT_DIR", "/tmp/mset-impact"))
pairs = json.loads((OUT / "pairs.json").read_text())
NAMES = {"1": "Mus musculus", "2": "Homo sapiens"}
ALPHA = 0.05

for sp in ("1", "2"):
    old_u = set(json.loads((OUT / f"old_universe_{sp}.json").read_text()))
    new_u = set(json.loads((OUT / f"new_universe_{sp}.json").read_text()))
    members = {
        int(k): set(v) for k, v in json.loads((OUT / f"members_{sp}.json").read_text()).items()
    }
    N_old, N_new = len(old_u), len(new_u)

    refused_old = runnable = 0
    shifts, flips_to_sig, flips_to_ns = [], 0, 0
    out_frac = []

    for pr in pairs[sp]:
        a, b = members[pr["a"]], members[pr["b"]]
        outside = (a | b) - old_u
        out_frac.append(len(outside) / len(a | b))
        if outside:
            # Legacy aborted: "list_N not subset of its background".
            refused_old += 1
            continue
        runnable += 1
        K, n, k = pr["K"], pr["n"], pr["k"]
        p_old = hypergeom.sf(k - 1, N_old, K, n)
        p_new = hypergeom.sf(k - 1, N_new, K, n)
        shifts.append((p_old, p_new))
        if p_old >= ALPHA > p_new:
            flips_to_sig += 1
        elif p_new >= ALPHA > p_old:
            flips_to_ns += 1

    print(f"\n=== {NAMES[sp]} (sp {sp}) — universe {N_old:,} -> {N_new:,} ({N_new / N_old:.2f}x)")
    print(f"  pairs sampled                     {len(pairs[sp])}")
    print(
        f"  OLD rule refused to run           {refused_old} ({refused_old / len(pairs[sp]):.0%}) "
        f"-- genes outside the curated background"
    )
    print(f"  both rules run                    {runnable}")
    if shifts:
        ratios = [(o / n) for o, n in shifts if n > 0]
        print(
            f"  p-value moves DOWN (more sig.)    {sum(1 for o, n in shifts if n < o)}/{len(shifts)}"
        )
        print(
            f"  p-value moves UP                  {sum(1 for o, n in shifts if n > o)}/{len(shifts)}"
        )
        if ratios:
            ratios.sort()
            print(
                f"  p_old/p_new  median {statistics.median(ratios):.2f}x   "
                f"p90 {ratios[int(0.9 * len(ratios)) - 1]:.2f}x   max {max(ratios):.1f}x"
            )
        print(
            f"  verdict flips at alpha={ALPHA}:   ns -> significant  {flips_to_sig} "
            f"({flips_to_sig / len(shifts):.0%});  significant -> ns  {flips_to_ns}"
        )
        both_sig = sum(1 for o, n in shifts if o < ALPHA and n < ALPHA)
        print(f"  significant under both            {both_sig}")
    print(
        f"  mean fraction of a pair's genes outside the old universe: "
        f"{statistics.mean(out_frac):.1%}"
    )
