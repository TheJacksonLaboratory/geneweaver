"""Validate the ported JaccardSimilarity tool against the legacy ``jac_pvalue`` on the DB.

JaccardSimilarity is a faithful refactor of
``legacy/tools-worker/tools/JaccardSimilarity.py`` onto ``AbstractTool``. The computation the
port owns is two functions: the Jaccard coefficient ``C / (A + B + C)`` and the empirical
p-value (fraction of a null Jaccard distribution >= the observed value). This script checks
both against a verbatim transcription of the legacy logic, using real gene-set pairs:

  - pairwise counts ``(only_i, only_j, intersection)`` are built from real membership pulled
    from the local DB (the legacy pairwise counting reduces to set algebra with no
    pairwise-deletion / homology);
  - the Jaccard coefficient is compared to the legacy formula on every pair (exact);
  - the empirical p-value is compared to a verbatim transcription of the legacy ``jac_pvalue``
    tally. ``extsrc.jaccard_distribution_results`` is **empty** on this DB, so the live path is
    vacuous (both return 0.0 / 0) -- so the tally is *also* exercised on a synthetic null
    distribution per pair to prove the port reproduces the legacy p-value, not just the
    no-distribution fallback.

Usage:
    uv run --extra sklearn --project packages/tools python \
        scripts/validation/validate_jaccard_similarity.py
"""

from __future__ import annotations

import itertools
import os
import sys

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "tools", "src"))
from geneweaver.tools.jaccard_similarity import (
    JaccardDistribution,
    JaccardSimilarity,
    JaccardSimilarityInput,
)
from geneweaver.tools.jaccard_similarity.schema import GenesetPairCounts

DSN = "host=127.0.0.1 port=5433 dbname=geneweaver-dev user=geneweaver-dev password=localdev"
GENESET_IDS = [514, 515, 648, 664, 32922, 32912, 32408, 34487, 34486, 32556]


def load_membership(cur):
    """geneset id -> set of member gene ids."""
    out = {}
    for gs_id in GENESET_IDS:
        cur.execute(
            "SELECT ode_gene_id FROM extsrc.geneset_value WHERE gs_id=%s AND gsv_in_threshold",
            (gs_id,),
        )
        out[str(gs_id)] = {str(r[0]) for r in cur.fetchall()}
    return out


def legacy_jac_coef(only_a, only_b, intersection):
    """Legacy mainexec: jac = 11/(10+01+11) when 11 != 0 else 0.0."""
    if intersection != 0:
        return float(intersection) / (float(only_a) + float(only_b) + float(intersection))
    return 0.0


def legacy_jac_pvalue(A, B, C, dist_rows):
    """Verbatim transcription of JaccardSimilarity.jac_pvalue (tally over a results list).

    ``dist_rows`` are ``(jaccard_coef, frequency)`` pairs (the legacy read these from
    ``extsrc.jaccard_distribution_results`` as ``r[3]``/``r[4]``).
    """
    if A == 0 and B == 0:
        return 1
    if A > B:
        A, B = B, A
    N = A + B + C
    J = float(C) / float(N)
    if not dist_rows:
        return 0
    freq_total = 1
    eg_magnitude = 1
    for rj, rf in dist_rows:
        if rj >= J:
            eg_magnitude += rf
        freq_total += rf
    return float(eg_magnitude) / freq_total


def synthetic_distribution(only_a, only_b, intersection):
    """Deterministic non-trivial null distribution straddling the observed Jaccard."""
    a, b = (only_a, only_b) if only_a <= only_b else (only_b, only_a)
    n = a + b + intersection
    obs = float(intersection) / n if n else 0.0
    rows = [
        (round(obs * 0.5, 6), 100),
        (round(obs, 6), 50),
        (round(min(obs * 1.5, 1.0), 6), 20),
        (round(min(obs * 2.0, 1.0), 6), 5),
    ]
    return a, b, rows


def main():
    """Build real pairs, compare port jaccard + empirical p-value vs the legacy transcription."""
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        sets = load_membership(cur)

    ids = list(sets)
    pairs = list(itertools.combinations(range(len(ids)), 2))

    # Build pairwise counts + synthetic distributions for every pair.
    pair_counts = []
    distributions = []
    seen_sizes = set()
    for i, j in pairs:
        a, b = sets[ids[i]], sets[ids[j]]
        only_i, only_j, inter = len(a - b), len(b - a), len(a & b)
        pair_counts.append(GenesetPairCounts(i=i, j=j, only_i=only_i, only_j=only_j, intersection=inter))
        sa, sb, rows = synthetic_distribution(only_i, only_j, inter)
        if (sa, sb) not in seen_sizes:
            seen_sizes.add((sa, sb))
            distributions.append(
                JaccardDistribution(set_size1=sa, set_size2=sb, homology=False, frequencies=rows)
            )

    print(f"{len(ids)} gene sets, {len(pairs)} pairs; "
          f"extsrc.jaccard_distribution_results is empty (live p-value path is vacuous)\n")

    # --- 1. coefficient + no-distribution (live) parity ---
    out_live = JaccardSimilarity().run(
        JaccardSimilarityInput(geneset_ids=ids, include_homology=False, pairs=pair_counts)
    )
    # The legacy mainexec only calls jac_pvalue when intersection (11) != 0; otherwise it sets
    # a sentinel and skips it. The port mirrors this: p_value is None when intersection == 0.
    coef_ok = skip_ok = 0
    coef_max_diff = 0.0
    for res in out_live.results:
        leg_jac = legacy_jac_coef(res.only_i, res.only_j, res.intersection)
        coef_max_diff = max(coef_max_diff, abs(res.jaccard - leg_jac))
        coef_ok += abs(res.jaccard - leg_jac) < 1e-12
        # intersection == 0 -> both skip the empirical p-value (port None, legacy sentinel)
        if res.intersection == 0:
            skip_ok += res.p_value is None

    # --- 2. empirical p-value parity on a synthetic null distribution (intersection > 0) ---
    out_dist = JaccardSimilarity().run(
        JaccardSimilarityInput(
            geneset_ids=ids, include_homology=False, pairs=pair_counts, distributions=distributions
        )
    )
    pval_ok = 0
    pval_max_diff = 0.0
    nonzero = sum(1 for r in out_dist.results if r.intersection != 0)
    n_zero = len(pairs) - nonzero
    for res in out_dist.results:
        if res.intersection == 0:
            continue
        _a, _b, rows = synthetic_distribution(res.only_i, res.only_j, res.intersection)
        leg_p = legacy_jac_pvalue(res.only_i, res.only_j, res.intersection, rows)
        port_p = res.p_value
        pval_max_diff = max(pval_max_diff, abs(port_p - float(leg_p)))
        pval_ok += abs(port_p - float(leg_p)) < 1e-12

    n = len(pairs)
    print(f"  jaccard coefficient == legacy        {coef_ok}/{n}   (max diff {coef_max_diff:.2e})")
    print(f"  p-value skipped when intersection=0  {skip_ok}/{n_zero}   (port None == legacy sentinel)")
    print(f"  empirical p (synthetic) == legacy    {pval_ok}/{nonzero}  (max diff {pval_max_diff:.2e}, "
          f"intersection>0 pairs)")

    ok = coef_ok == n and skip_ok == n_zero and pval_ok == nonzero
    print("\nRESULT:", "PORT MATCHES LEGACY ✓" if ok else "MISMATCHES FOUND ✗")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
