"""Does a Tier-IV gene set legacy refuses run on v3? (G3-784 acceptance; GWC-51 / G3-783)

Run inside a v3 native tools worker pod. Builds the request as the API does -- member
symbols plus a universe *reference* -- expands it through the worker's resolver, and runs
the real ``MSETcpp`` through the v3 ``MSET`` tool, with every gene and with the uploader's
threshold. Read-only on the database.

Usage: ``python tier4_check.py 407805,218676 [more pairs...]``
"""

import json
import sys
import time

from geneweaver.db.query.membership import ALL_GENES, Thresholds
from geneweaver.db.tool_input import gene_symbols_by_geneset
from geneweaver.tools.mset import MSET, MSETInput, genes_outside_background
from geneweaver.tools.temporal.db import cursor as db_cursor
from geneweaver.tools.temporal.resolvers import resolve_input


def main() -> None:
    """Run MSET on each pair under both membership choices and print the outcome."""
    pairs = [tuple(int(gs_id) for gs_id in arg.split(",")) for arg in sys.argv[1:]]
    for first, second in pairs:
        for label, thresholds in (
            ("all genes", ALL_GENES),
            ("uploader threshold", Thresholds(mode="uploader")),
        ):
            with db_cursor() as cursor:
                members = gene_symbols_by_geneset(cursor, [first, second], thresholds)
            request = {
                "tool": "mset",
                "input": {
                    "group_1_genes": members[str(first)],
                    "group_2_genes": members[str(second)],
                },
                "universe": {"geneset_ids": [first, second]},
            }
            resolved = resolve_input("mset", request)
            universe = resolved["group_1_background"]
            started = time.time()
            try:
                output = MSET().run(MSETInput(**resolved))
                outcome = {
                    "status": "OK",
                    "intersect": len(output.intersect_genes),
                    "mset_data": output.mset_data,
                }
            except Exception as exc:  # reported, not hidden
                outcome = {"status": "FAILED", "error": str(exc)[:400]}
            print(
                json.dumps(
                    {
                        "pair": [first, second],
                        "membership": label,
                        "list_sizes": [len(members[str(first)]), len(members[str(second)])],
                        "universe_size": len(universe),
                        "genes_outside_universe": [
                            len(genes_outside_background(resolved[f"group_{i}_genes"], universe))
                            for i in (1, 2)
                        ],
                        "seconds": round(time.time() - started, 2),
                        **outcome,
                    }
                )
            )


if __name__ == "__main__":
    main()
