"""Validate the ported MSET tool's Python surface against the legacy MSET.py on the DB.

MSET is a binary-wrapper port (like DBSCAN): the Monte-Carlo enrichment test itself runs in
the shared ``TOOLBOX/CS_Mset/MSETcpp`` binary, so there is no Python algorithm to benchmark.
What the port *owns* in Python is three things, all validated here against
``legacy/tools-worker/tools/MSET.py``:

  1. ``intersect_genes`` -- the shared genes between the two input lists. Validated on real
     gene-set membership from the local DB against the legacy ``np.intersect1d`` (same set;
     the port additionally preserves group-1 order and de-duplicates).
  2. ``parse_tsv_dict`` -- parsing the binary's ``mset_output.tsv`` / ``mset_hist.tsv``.
     Validated against the legacy ``tsv_file_to_dict`` on a representative TSV.
  3. The documented **bug fix**: the legacy used ``group_1_background`` for *both* gene lists
     (copy-paste bug, MSET.py line ~69); the port correctly passes ``group_2_background`` for
     list 2. Verified via a capturing runner (no binary needed).

Usage:
    uv run --extra sklearn --project packages/tools python \
        scripts/validation/validate_mset.py
"""

from __future__ import annotations

import os
import sys
import tempfile

import numpy as np
import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "tools", "src"))
from geneweaver.tools.mset import MSET, MSETInput
from geneweaver.tools.mset import tool as mset_tool
from geneweaver.tools.mset.tool import intersect_genes, parse_tsv_dict

DSN = "host=127.0.0.1 port=5433 dbname=geneweaver-dev user=geneweaver-dev password=localdev"
GROUP_1_GS = 32922
GROUP_2_GS = 32912


def load_genes(cur, gs_id):
    """Member gene ids (str) of a gene set, ordered by id (as the tools receive them)."""
    cur.execute(
        "SELECT ode_gene_id FROM extsrc.geneset_value WHERE gs_id=%s AND gsv_in_threshold "
        "ORDER BY ode_gene_id",
        (gs_id,),
    )
    return [str(r[0]) for r in cur.fetchall()]


def legacy_tsv_file_to_dict(path):
    """Verbatim transcription of MSET.tsv_file_to_dict."""
    with open(path) as tsv_file:
        return {row[0]: row[1:][0].strip() for row in (line.split("\t") for line in tsv_file)}


def main():
    """Validate intersect_genes, TSV parsing, and the group_2_background bug fix."""
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        list_1 = load_genes(cur, GROUP_1_GS)
        list_2 = load_genes(cur, GROUP_2_GS)

    print(f"group 1 (GS{GROUP_1_GS}): {len(list_1)} genes, "
          f"group 2 (GS{GROUP_2_GS}): {len(list_2)} genes\n")

    # --- 1. intersect_genes: same set as legacy np.intersect1d ---
    port_inter = intersect_genes(list_1, list_2)
    legacy_inter = np.intersect1d(list_1, list_2).tolist()
    set_ok = set(port_inter) == set(legacy_inter)
    order_ok = port_inter == [g for g in list_1 if g in set(list_2)]  # group-1 order, deduped
    no_dups = len(port_inter) == len(set(port_inter))
    print(f"  intersect_genes == legacy (as set)   {'OK' if set_ok else 'MISMATCH'}   "
          f"(|∩|={len(port_inter)}; legacy np.intersect1d={len(legacy_inter)})")
    print(f"  intersect_genes preserves grp-1 order {'OK' if order_ok and no_dups else 'X'}   "
          f"(port keeps input order + de-dups; legacy returns sorted-unique)")

    # --- 2. parse_tsv_dict == legacy tsv_file_to_dict ---
    sample = "MSET p-value\t0.0023\nObserved intersection\t7\nExpected mean\t2.41\nTrials\t1000\n"
    fd, tsv_path = tempfile.mkstemp(suffix=".tsv")
    with os.fdopen(fd, "w") as fh:
        fh.write(sample)
    port_parsed = parse_tsv_dict(sample)
    legacy_parsed = legacy_tsv_file_to_dict(tsv_path)
    os.unlink(tsv_path)
    parse_ok = port_parsed == legacy_parsed
    print(f"  parse_tsv_dict == legacy parser       {'OK' if parse_ok else 'MISMATCH'}   "
          f"({len(port_parsed)} keys: {sorted(port_parsed)})")

    # --- 3. group_2_background bug fix (capturing runner; no binary needed) ---
    # The backgrounds are now resolved gene universes rather than *BG.txt file names
    # (G3-784), so each list gets its own universe: here, itself.
    captured: dict = {}

    def capturing_runner(g1, g2, bg1, bg2, n_samples, over):
        captured.update(bg1=bg1, bg2=bg2, n=n_samples, over=over)
        return ("k\tv\n", "k\tv\n")

    MSET(runner=capturing_runner).run(
        MSETInput(
            group_1_genes=list_1,
            group_2_genes=list_2,
            group_1_background=list(list_1),
            group_2_background=list(list_2),
            number_of_samples=100,
        )
    )
    bug_fixed = captured.get("bg1") == list(list_1) and captured.get("bg2") == list(list_2)
    print(f"  list-2 uses group_2_background (fix)  {'OK' if bug_fixed else 'MISMATCH'}   "
          f"(port bg2 has {len(captured.get('bg2') or [])} genes; legacy reused "
          f"group_1_background here)")

    # --- 4. the background is data, not a file path (G3-784) ---
    no_file_dependency = (
        "group_1_background" in MSETInput.model_fields
        and MSETInput.model_fields["group_1_background"].annotation is not str
        and not hasattr(mset_tool, "BACKGROUND_ENV_VAR")
    )
    print(f"  background passed as data, not a file  {'OK' if no_file_dependency else 'MISMATCH'}   "
          f"(no GENEWEAVER_MSET_BACKGROUND_DIR; no *BG.txt read at run time)")

    # --- 5. out-of-universe genes fail legibly rather than cryptically (GWC-51) ---
    try:
        MSET(runner=capturing_runner).run(
            MSETInput(
                group_1_genes=[*list_1, "__NOT_A_REAL_GENE__"],
                group_2_genes=list_2,
                group_1_background=list(list_1),
                group_2_background=list(list_2),
            )
        )
        subset_checked = False
    except ValueError as exc:
        subset_checked = "__NOT_A_REAL_GENE__" in str(exc)
    print(f"  out-of-universe gene named in error   {'OK' if subset_checked else 'MISMATCH'}   "
          f"(legacy surfaced MSETcpp's \"list_N not subset of its background\")")

    ok = (set_ok and order_ok and no_dups and parse_ok and bug_fixed
          and no_file_dependency and subset_checked)
    print("\nRESULT:", "PORT PYTHON SURFACE MATCHES LEGACY (+ bug fixed) ✓" if ok else "MISMATCHES ✗")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
