"""HyperGeometric: legacy incremental-float `combtl` Fisher vs. the `math.comb` port.

The port's improvement is *correctness* (exact integer binomials + the fixed per-tail reset),
already shown in scripts/validation/validate_hypergeometric.py. This quantifies the speed
trade-off: exact `math.comb` uses big integers (slower per op, no precision loss) vs. the
legacy cached incremental-float `combtl` (fast, but loses precision and accumulates the
documented bug). Honest accounting -- the Python win here is accuracy, not necessarily speed.

Usage:
    uv run --project packages/tools python scripts/benchmarks/bench_hypergeometric.py
"""
# ruff: noqa: D103  (benchmark script; transcribed legacy code)

from __future__ import annotations

import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "tools", "src"))
from geneweaver.tools.hypergeometric.tool import fisher_exact_2x2


class _Legacy:
    def __init__(self):
        self._comb_cache = {}

    def combtl(self, n, r):
        if r == 0:
            return 1
        key = (n, r)
        if key in self._comb_cache:
            return self._comb_cache[key]
        r = min(r, n - r)
        i, j, cnr = n - r + 1, 1, 1
        while i <= n or j <= r:
            if i <= n:
                cnr *= i
                i += 1
            if j <= r:
                cnr /= j
                j += 1
        self._comb_cache[key] = cnr
        return cnr

    def fisher(self, f00, f01, f10, f11):
        f00, f01, f10, f11 = float(f00), float(f01), float(f10), float(f11)
        f0, g0, g1 = f00 + f01, f00 + f10, f01 + f11
        ft = f00 + f01 + f10 + f11
        C = self.combtl(ft, f0)
        prob = (self.combtl(g0, f00) * self.combtl(g1, f01)) / C
        pval = prob
        out = {}
        for tail in ("ut", "lt", "tt"):
            a_max = min(f0, g0)
            a_start, a_end = 0, a_max
            if tail == "lt":
                a_end = f00 - 1
            elif tail == "ut":
                a_start = f00 + 1
            for a in range(int(a_start), int(a_end) + 1):
                if a == f00:
                    continue
                b, c = f0 - a, g0 - a
                d = g1 - b
                if d < 0:
                    continue
                p = (self.combtl(a + c, a) * self.combtl(b + d, b)) / C
                if p < prob:
                    pval += p
            out[tail] = min(pval, 1.0)
        return out


def make_tables(n_tables, universe, seed=0):
    """Random 2x2 contingency tables summing to `universe`."""
    rng = random.Random(seed)
    tables = []
    for _ in range(n_tables):
        f11 = rng.randint(0, universe // 4)
        f10 = rng.randint(0, universe // 4)
        f01 = rng.randint(0, universe // 4)
        f00 = universe - f11 - f10 - f01
        tables.append((f00, f01, f10, f11))
    return tables


def main():
    print("=== HyperGeometric: legacy combtl-float vs port math.comb (200 tables each) ===")
    header = f"{'universe':>8} | {'legacy(ms)':>11} | {'port(ms)':>9} | {'ratio':>6} | note"
    print(header)
    print("-" * (len(header) + 8))
    for universe in [50, 100, 200, 400, 800]:
        tables = make_tables(200, universe)

        legacy = _Legacy()
        t0 = time.perf_counter()
        for f00, f01, f10, f11 in tables:
            legacy.fisher(f00, f01, f10, f11)
        legacy_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        for f00, f01, f10, f11 in tables:
            fisher_exact_2x2(f00, f01, f10, f11)
        port_ms = (time.perf_counter() - t0) * 1000

        ratio = legacy_ms / port_ms if port_ms else float("inf")
        faster = "port faster" if ratio > 1 else "legacy faster (float vs bigint)"
        print(f"{universe:>8} | {legacy_ms:>11.1f} | {port_ms:>9.1f} | {ratio:>5.2f}x | {faster}")

    print("\n  (correctness, not speed, is the point: the port fixes the lt/tt accumulation")
    print("   bug and uses exact integers -- see scripts/validation/validate_hypergeometric.py)")


if __name__ == "__main__":
    main()
