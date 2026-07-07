"""PhenomeMap link score: legacy hand-rolled KS vs. scipy.stats.ks_2samp.

The port briefly swapped the legacy hand-rolled two-sample Kolmogorov-Smirnov approximation
for `scipy.stats.ks_2samp`. This benchmark is *why that swap was reverted*: it shows scipy is
both slower AND numerically different (scipy defaults to the *exact* p-value, diverging from
the legacy *asymptotic* form by up to ~0.1 for small samples; `method='asymp'` is closer but
still not identical). The port now keeps a pure-Python transcription of the legacy asymptotic
KS (`tool.ks_2samp_pvalue`), which is faithful and faster. See TOOLS_BENCHMARKS.md §4.

Usage:
    uv run --extra sklearn --project packages/tools python \
        scripts/benchmarks/bench_phenomemap_ks.py
"""
# ruff: noqa: D103  (benchmark script; transcribed legacy code)

from __future__ import annotations

import random
import time

import numpy as np
from scipy.stats import ks_2samp as scipy_ks

# legacy hand-rolled KS (verbatim from PhenomeMap.py)
KS_CONST = -((np.arange(1, 7, 2, dtype=float) * np.pi) ** 2) / 8


def legacy_ks(data1, data2):
    data1 = np.asarray(data1)
    data2 = np.asarray(data2)
    data1.sort()
    data2.sort()
    n1, n2 = float(data1.size), float(data2.size)
    data_all = np.concatenate([data1, data2])
    cdf1 = np.searchsorted(data1, data_all, side="right") / n1
    cdf2 = np.searchsorted(data2, data_all, side="right") / n2
    d = np.max(np.absolute(cdf1 - cdf2))
    if d > np.finfo("float").eps:
        en = np.sqrt(n1 * n2 / (n1 + n2))
        prob = 1 - np.sqrt(2 * np.pi) / ((en + 0.12 + 0.11 / en) * d) * np.sum(
            np.exp(KS_CONST / ((en + 0.12 + 0.11 / en) * d) ** 2)
        )
    else:
        prob = 1.0
    return d, prob


def main():
    print("=== PhenomeMap KS: legacy hand-rolled vs scipy.stats.ks_2samp (2000 calls each) ===")
    header = f"{'sample n':>8} | {'legacy(ms)':>11} | {'scipy(ms)':>10} | {'max |Δp|':>10}"
    print(header)
    print("-" * len(header))
    rng = random.Random(0)
    for n in [10, 50, 200, 1000]:
        pairs = [
            (
                [rng.gauss(0, 1) for _ in range(n)],
                [rng.gauss(0.3, 1) for _ in range(n)],
            )
            for _ in range(2000)
        ]

        t0 = time.perf_counter()
        legacy_p = [legacy_ks(a, b)[1] for a, b in pairs]
        legacy_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        scipy_p = [float(scipy_ks(a, b).pvalue) for a, b in pairs]
        scipy_ms = (time.perf_counter() - t0) * 1000

        max_dp = max(abs(lp - sp) for lp, sp in zip(legacy_p, scipy_p, strict=True))
        print(f"{n:>8} | {legacy_ms:>11.1f} | {scipy_ms:>10.1f} | {max_dp:>10.2e}")

    print("\n  (scipy is slower and the p-values diverge for small n, so the port keeps the")
    print("   faithful legacy asymptotic KS -- pure-Python tool.ks_2samp_pvalue, no scipy)")


if __name__ == "__main__":
    main()
