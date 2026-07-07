"""Validate the ported Combine tool against the legacy ``combine_genesets`` on the local DB.

Combine is a faithful refactor: the port (``geneweaver.tools.combine``) transcribes
``legacy/tools-worker/tools/toolbase.py::combine_genesets`` (the legacy ``Combine.mainexec``
was a no-op) onto ``AbstractTool``, with the three ``TOOLSET_SQL`` queries lifted out to the
caller. This script runs both on the same real rows from the local DB:

  - membership / homology-pair / label rows come from the legacy ``TOOLSET_SQL[0..2]`` run
    verbatim under the legacy ``search_path``;
  - ``combine_genesets`` is transcribed verbatim below (building the matrix incl. the legacy
    ``'==HEADER=='`` entry);
  - the port's gene x gene-set matrix + gs labels/names are compared against that reference.

(``extsrc.homology`` is empty, so the homolog-merge branch is a no-op here -- matrix keys stay
positive -- but the membership matrix build and the label/name extraction are exercised over
real data.)

Usage:
    uv run --extra sklearn --project packages/tools python \
        scripts/validation/validate_combine.py
"""

# ruff: noqa: SIM102  (validation script; legacy combine_genesets transcribed verbatim)

from __future__ import annotations

import os
import re
import sys

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "tools", "src"))
from geneweaver.tools.combine import Combine, CombineInput

DSN = "host=127.0.0.1 port=5433 dbname=geneweaver-dev user=geneweaver-dev password=localdev"
GENESET_IDS = [514, 515, 648, 664, 32922, 32912, 32408, 34487, 34486, 32556]

# Legacy TOOLSET_SQL[0..2], verbatim from toolbase.py (rely on the search_path).
TOOLSET_SQL = [
    r"""SELECT gs_id, gsv.ode_gene_id, ode_ref_id FROM geneset_value gsv, gene gid
    WHERE gsv_in_threshold AND gs_id=ANY(%s) AND gsv.ode_gene_id=gid.ode_gene_id AND gid.ode_pref;""",
    r"""SELECT a.ode_gene_id as "left_ode_gene_id", b.ode_gene_id as "right_ode_gene_id", a.hom_id
    FROM homology a, homology b
    WHERE a.hom_id=b.hom_id and a.ode_gene_id<>b.ode_gene_id
     AND a.ode_gene_id IN (SELECT DISTINCT ode_gene_id FROM geneset_value WHERE gsv_in_threshold and gs_id=ANY(%s))
     AND b.ode_gene_id IN (SELECT DISTINCT ode_gene_id FROM geneset_value WHERE gsv_in_threshold and gs_id=ANY(%s))
    GROUP BY left_ode_gene_id, right_ode_gene_id, a.hom_id
    """,
    r"SELECT gs_id, gs_name, gs_abbreviation FROM geneset WHERE gs_id=ANY(%s);",
]


def legacy_combine_genesets(data1, data2, data3, gsids, include_homology):
    """Verbatim transcription of toolbase.combine_genesets (matrix incl. '==HEADER==')."""
    matrix: dict = {}
    for row in data1:
        if row[1] not in matrix:
            matrix[row[1]] = {}
        matrix[row[1]][0] = row[2]
        matrix[row[1]][row[0]] = 1

    homologs: dict = {}
    h2: dict = {}
    if len(data2) > 0 and include_homology:
        for row in data2:
            if row[0] not in homologs:
                homologs[row[0]] = {}
            if row[1] not in homologs:
                homologs[row[1]] = {}
            homologs[row[0]][row[1]] = 1
            homologs[row[1]][row[0]] = 1
        for h, arr in homologs.items():
            cnt = len(arr) + 1
            h2.setdefault(cnt, []).append(h)
        h2counts = sorted(h2.keys(), reverse=True)
        for cnt in h2counts:
            for candidate in h2[cnt]:
                if candidate in homologs and candidate in matrix:
                    r3 = matrix[candidate]
                    added = False
                    for g2 in list(homologs[candidate].keys()):
                        if g2 not in matrix:
                            continue
                        for gsid in gsids:
                            if gsid in matrix[g2] and matrix[g2][gsid]:
                                if gsid not in r3 or not r3[gsid]:
                                    r3[gsid] = 1
                                    added = True
                        del matrix[g2]
                        del homologs[g2]
                    if added:
                        matrix[-candidate] = r3
                        del matrix[candidate]

    header = {"gsids": gsids, "gslabels": {}, "gsnames": {}}
    for row in data3:
        header["gslabels"][row[0]] = re.sub("[\t\n]", " ", row[2])
        header["gsnames"][row[0]] = re.sub("[\t\n]", " ", row[1])
    matrix["==HEADER=="] = header
    return matrix


def main():
    """Pull the three legacy result sets, run port + legacy, and compare the matrix + labels."""
    gsids_str = "{" + ",".join(str(g) for g in GENESET_IDS) + "}"
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("SET search_path TO production,extsrc,odestatic;")
        cur.execute(TOOLSET_SQL[0], (gsids_str,))
        data1 = [list(r) for r in cur.fetchall()]
        cur.execute(TOOLSET_SQL[1], (gsids_str, gsids_str))
        data2 = [list(r) for r in cur.fetchall()]
        cur.execute(TOOLSET_SQL[2], (gsids_str,))
        data3 = [list(r) for r in cur.fetchall()]
        conn.rollback()

    print(
        f"data: {len(data1)} membership rows, {len(data2)} homology pairs, "
        f"{len(data3)} label rows over {len(GENESET_IDS)} gene sets "
        f"(homology empty -> merge is a no-op)\n"
    )

    port = Combine().run(
        CombineInput(
            geneset_ids=GENESET_IDS,
            include_homology=True,
            membership_rows=[list(r) for r in data1],
            homology_pairs=[list(r) for r in data2],
            label_rows=[list(r) for r in data3],
        )
    )

    legacy = legacy_combine_genesets(data1, data2, data3, GENESET_IDS, include_homology=True)
    legacy_header = legacy.pop("==HEADER==")

    checks = {
        "matrix": port.matrix == legacy,
        "gslabels": port.gslabels == legacy_header["gslabels"],
        "gsnames": port.gsnames == legacy_header["gsnames"],
    }
    ok = all(checks.values())
    print(f"  matrix genes      port={len(port.matrix):<5d} legacy={len(legacy):<5d} "
          f"{'OK' if checks['matrix'] else 'MISMATCH'}")
    print(f"  gslabels          port={len(port.gslabels):<5d} legacy={len(legacy_header['gslabels']):<5d} "
          f"{'OK' if checks['gslabels'] else 'MISMATCH'}")
    print(f"  gsnames           port={len(port.gsnames):<5d} legacy={len(legacy_header['gsnames']):<5d} "
          f"{'OK' if checks['gsnames'] else 'MISMATCH'}")

    print("\nRESULT:", "ALL CHECKS MATCH ✓" if ok else "MISMATCHES FOUND ✗")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
