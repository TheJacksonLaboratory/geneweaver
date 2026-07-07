"""Validate the ported UpSet tool against the legacy py-upset intersection semantics.

UpSet is a faithful refactor of ``legacy/tools-worker/tools/UpSet.py``, whose intersection
computation is delegated to the bundled py-upset code (``UpSetOriginal.py``). py-upset's
``extract_intersection_data`` computes, for each non-empty combination of the gene sets, the
**exclusive** intersection -- genes in *all* of the in-sets and *none* of the out-sets -- and
its size. (The legacy code itself can't run on modern pandas: it uses the removed
``DataFrame.ix`` accessor.) This script transcribes that exclusive-intersection set algebra as
the reference and compares it to the port over real membership from the local DB, for both
``include_zeros`` modes (the legacy ``mainexec`` keeps an intersection iff ``size > 0`` or
zero-size intersections are explicitly included).

Usage:
    uv run --extra sklearn --project packages/tools python \
        scripts/validation/validate_upset.py
"""

from __future__ import annotations

import os
import sys
from itertools import combinations

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "tools", "src"))
from geneweaver.tools.upset import UpSet, UpSetInput

DSN = "host=127.0.0.1 port=5433 dbname=geneweaver-dev user=geneweaver-dev password=localdev"
# Gene sets with graded overlap -> non-trivial multi-way intersections.
GENESET_IDS = [32922, 32912, 32408, 34487, 34486, 32556]


def load_memberships(cur):
    """geneset id (str) -> list of member gene ids (str), non-homology path."""
    out = {}
    for gs_id in GENESET_IDS:
        cur.execute(
            "SELECT ode_gene_id FROM extsrc.geneset_value WHERE gs_id=%s AND gsv_in_threshold",
            (gs_id,),
        )
        out[str(gs_id)] = [str(r[0]) for r in cur.fetchall()]
    return out


def legacy_upset(memberships, include_zeros):
    """py-upset exclusive-intersection sizes per non-empty combination (transcribed semantics).

    Returns ``{frozenset(combo): size}`` where size = the count of genes in *all* of the
    in-sets and *none* of the out-sets, keeping zero-size combinations only when
    ``include_zeros`` (mirrors the legacy mainexec filter).
    """
    ids = list(memberships)
    sets = {k: set(v) for k, v in memberships.items()}
    result = {}
    for r in range(1, len(ids) + 1):
        for combo in combinations(ids, r):
            in_sets = set(combo)
            out_sets = set(ids) - in_sets
            exclusive = set(sets[combo[0]])
            for s in combo[1:]:
                exclusive &= sets[s]
            for s in out_sets:
                exclusive -= sets[s]
            size = len(exclusive)
            if size > 0 or include_zeros:
                result[frozenset(combo)] = size
    return result


def port_dict(output):
    """Map the port's intersections to ``{frozenset(genesets): size}``."""
    return {frozenset(i.genesets): i.size for i in output.intersections}


def main():
    """Pull membership, run port vs the transcribed py-upset reference for both zero modes."""
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        memberships = load_memberships(cur)

    n_genes = len({g for v in memberships.values() for g in v})
    print(f"{len(memberships)} gene sets, {n_genes} distinct genes\n")

    tool = UpSet()
    all_ok = True
    for include_zeros in (False, True):
        port = port_dict(
            tool.run(
                UpSetInput(
                    geneset_ids=list(memberships),
                    gene_memberships=memberships,
                    include_zeros=include_zeros,
                )
            )
        )
        legacy = legacy_upset(memberships, include_zeros)
        ok = port == legacy
        all_ok &= ok
        if not ok:
            only_p = set(port) - set(legacy)
            only_l = set(legacy) - set(port)
            diff_sz = {k: (port[k], legacy[k]) for k in set(port) & set(legacy) if port[k] != legacy[k]}
            print(f"  include_zeros={include_zeros!s:<5} MISMATCH  port-only={len(only_p)} "
                  f"legacy-only={len(only_l)} size-diffs={len(diff_sz)}")
        else:
            print(f"  include_zeros={include_zeros!s:<5} intersections={len(port):<4d} "
                  f"(genes accounted: {sum(port.values())})  OK")

    print("\nRESULT:", "ALL CASES MATCH ✓" if all_ok else "MISMATCHES FOUND ✗")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
