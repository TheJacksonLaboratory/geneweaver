"""Validate the ported HyperGeometric (Fisher's exact) tool against legacy + an oracle.

The port deliberately diverges from the legacy in two ways (documented in the tool): it
uses exact ``math.comb`` instead of the legacy incremental-float ``combtl``, and it fixes a
real bug where the legacy reused ``pval`` across the upper/lower/two-tailed loop so the
lower- and two-tailed values accumulated. So "validate against legacy" here means:

  - **odds ratio** matches the legacy exactly (same formula, no combinatorics);
  - **upper tail** matches the legacy ``ut`` (the one tail computed before the accumulation
    bug pollutes it), within combtl float tolerance;
  - the legacy ``lt``/``tt`` bug is confirmed (legacy lt accumulated the upper-extreme mass,
    so legacy lt >= the correct lower), and the port resets per tail;
  - the port's two-tailed matches ``scipy.stats.fisher_exact`` (the gold standard), and its
    upper/lower match an independent ``scipy.stats.hypergeom`` pmf oracle using the same tail
    definition the legacy/port use -- proving the port is correct, not just different.

Real 2x2 contingency tables are built from gene-set pairs over the local DB (universe =
union of genes across the selected gene sets, as in the legacy odemat).

Usage:
    GENEWEAVER_HGEO_GRAPH_JSON=/tmp/hgeo_graph.json \
    python scripts/validation/validate_hypergeometric.py
"""

from __future__ import annotations

import itertools
import json
import os
import sys

import psycopg
from scipy.stats import fisher_exact, hypergeom

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "tools", "src"))
from geneweaver.tools.hypergeometric import (
    ContingencyCounts,
    HyperGeometric,
    HyperGeometricInput,
)

DSN = "host=127.0.0.1 port=5433 dbname=geneweaver-dev user=geneweaver-dev password=localdev"
GENESET_IDS = [514, 515, 648, 664, 32922, 32912, 32408, 34487, 34486, 32556]


# --- legacy combtl + fisher (verbatim from HyperGeometric.py) ---------------------------


class _Legacy:
    def __init__(self):
        self._comb_cache = {}

    def combtl(self, n, r):
        if r == 0:
            return 1
        key = "%d,%d" % (n, r)  # noqa: UP031  (kept verbatim from the legacy combtl)
        if key in self._comb_cache:
            return self._comb_cache[key]
        r = min(r, n - r)
        i = n - r + 1
        j = 1
        cnr = 1
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
        ret = {"or": (f00 * f11)}
        if f01 != 0 and f10 != 0:
            ret["or"] /= f01 * f10
        else:
            ret["or"] = "Inf"
        f0 = f00 + f01
        g0 = f00 + f10
        g1 = f01 + f11
        ft = f00 + f01 + f10 + f11
        C = self.combtl(ft, f0)
        prob = (self.combtl(g0, f00) * self.combtl(g1, f01)) / C
        pval = prob
        for i in ("ut", "lt", "tt"):
            a_max = min(f0, g0)
            a_start = 0
            a_end = a_max
            if i == "lt":
                a_end = f00 - 1
            elif i == "ut":
                a_start = f00 + 1
            for a in range(int(a_start), int(a_end) + 1):
                if a == f00:
                    continue
                b = f0 - a
                c = g0 - a
                d = g1 - b
                if d < 0:
                    continue
                p = (self.combtl(a + c, a) * self.combtl(b + d, b)) / C
                if p < prob:
                    pval += p
            if pval > 1:
                pval = 1.0
            ret[i] = pval
        return ret


def load_gene_symbols(cur):
    """geneset id -> set of member gene ids for the selected gene sets."""
    out = {}
    for gs_id in GENESET_IDS:
        cur.execute(
            "SELECT ode_gene_id FROM extsrc.geneset_value WHERE gs_id = %s AND gsv_in_threshold",
            (gs_id,),
        )
        out[str(gs_id)] = {str(r[0]) for r in cur.fetchall()}
    return out


def main():
    """Build contingency tables from the gene sets and compare port vs legacy vs scipy."""
    graph_json = os.environ.get("GENEWEAVER_HGEO_GRAPH_JSON")
    if graph_json:
        with open(graph_json) as fh:
            sets = {k: set(v) for k, v in json.load(fh).items()}
    else:
        with psycopg.connect(DSN) as conn, conn.cursor() as cur:
            sets = load_gene_symbols(cur)

    universe = set().union(*sets.values())
    n_universe = len(universe)
    ids = list(sets)
    legacy = _Legacy()
    tool = HyperGeometric()

    def oracle_tails(f00, f01, f10, f11):
        """Independent oracle: scipy.stats.hypergeom pmf + the (legacy) tail rule.

        The port/legacy tail = observed_p + the more-extreme-on-that-side configurations
        (p < observed); the two-tailed = all configurations with p <= observed. Computed
        here from scipy's pmf (an implementation independent of the port's math.comb).
        """
        f0, g0, ft = f00 + f01, f00 + f10, f00 + f01 + f10 + f11
        a_max = min(f0, g0)
        rv = hypergeom(ft, g0, f0)  # M, n, N -> P(a) = C(g0,a)C(g1,f0-a)/C(ft,f0)
        obs = rv.pmf(f00)
        upper = obs + sum(rv.pmf(a) for a in range(f00 + 1, a_max + 1) if rv.pmf(a) < obs)
        lower = obs + sum(rv.pmf(a) for a in range(0, f00) if rv.pmf(a) < obs)
        return min(upper, 1.0), min(lower, 1.0)

    or_ok = ut_ok = bug_ok = two_ok = up_ok = low_ok = 0
    legacy_tt_differs = 0
    pairs = list(itertools.combinations(range(len(ids)), 2))
    ut_max_diff = two_max_diff = up_max_diff = low_max_diff = 0.0

    for i, j in pairs:
        a, b = sets[ids[i]], sets[ids[j]]
        f11, f10, f01 = len(a & b), len(a - b), len(b - a)
        f00 = n_universe - len(a | b)

        leg = legacy.fisher(f00, f01, f10, f11)
        res = tool.run(
            HyperGeometricInput(
                geneset_ids=ids,
                pairs=[ContingencyCounts(i=i, j=j, f00=f00, f01=f01, f10=f10, f11=f11)],
            )
        ).results[0]

        # scipy fisher_exact two-sided (gold-standard, orientation-robust)
        sci_two = fisher_exact([[f00, f01], [f10, f11]])[1]
        # independent hypergeom-pmf oracle for the port's one-sided tail definition
        ora_up, ora_low = oracle_tails(f00, f01, f10, f11)

        # 1) odds ratio == legacy (exact)
        if leg["or"] == "Inf":
            or_ok += res.odds_ratio is None
        else:
            or_ok += res.odds_ratio is not None and abs(res.odds_ratio - leg["or"]) < 1e-9

        # 2) upper tail == legacy ut (legacy's one correct, un-accumulated tail)
        d = abs(res.upper_tail - leg["ut"])
        ut_max_diff = max(ut_max_diff, d)
        ut_ok += d < 1e-9

        # 3) legacy lt accumulated (>= the correct lower) -> bug present in legacy, fixed in port
        bug_ok += leg["lt"] >= res.lower_tail - 1e-12

        # 4) port two-tailed == scipy fisher_exact (independent gold standard)
        d2 = abs(res.two_tailed - sci_two)
        two_max_diff = max(two_max_diff, d2)
        two_ok += d2 < 1e-9

        # 5) port upper/lower == independent scipy-pmf oracle (same tail definition)
        du = abs(res.upper_tail - ora_up)
        dl = abs(res.lower_tail - ora_low)
        up_max_diff = max(up_max_diff, du)
        low_max_diff = max(low_max_diff, dl)
        up_ok += du < 1e-9
        low_ok += dl < 1e-9

        if abs(leg["tt"] - sci_two) > 1e-6:
            legacy_tt_differs += 1

    n = len(pairs)
    print(f"universe={n_universe} genes, {len(ids)} gene sets, {n} pairs\n")
    print(f"  odds ratio == legacy                 {or_ok}/{n}")
    print(f"  upper tail == legacy ut              {ut_ok}/{n}   (max diff {ut_max_diff:.2e})")
    print(f"  legacy lt accumulated >= port lower  {bug_ok}/{n}   (legacy bug; port resets)")
    print(f"  port two-tailed == scipy fisher      {two_ok}/{n}   (max diff {two_max_diff:.2e})")
    print(f"  port upper == hypergeom-pmf oracle   {up_ok}/{n}   (max diff {up_max_diff:.2e})")
    print(f"  port lower == hypergeom-pmf oracle   {low_ok}/{n}   (max diff {low_max_diff:.2e})")
    print(
        f"\n  (legacy two-tailed differs from the correct value in {legacy_tt_differs}/{n} "
        f"pairs -- the accumulation bug the port fixes)"
    )

    ok = or_ok == ut_ok == bug_ok == two_ok == up_ok == low_ok == n
    print("\nRESULT:", "PORT MATCHES LEGACY (where correct) + ORACLE ✓" if ok else "MISMATCHES ✗")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
