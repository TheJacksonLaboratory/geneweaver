"""v3 half of the MSET comparison (G3-784): run inside a v3 native tools worker pod.

Reads ``legacy_side.py``'s output and reruns each pair through the v3 path -- member lists
from ``geneweaver.db.tool_input`` with the uploader's threshold (legacy's
``gsv_in_threshold``), then the v3 ``MSET`` tool and the real ``MSETcpp`` -- twice:

* against **legacy's background** (the same universe, so it should agree with legacy to
  within Monte Carlo error: this checks the port);
* against the universe the worker's resolver produces, the **full gene space** for the
  species (the G3-784 rule: this measures the rule change).

Read-only on the database.

Environment:

* ``MSET_LEGACY_BG_DIR`` -- a directory holding legacy's ``GeneSymbol<Species>BG.txt`` files,
  copied from the legacy pod (required).
* the worker's own database settings (``DB_HOST`` and the rest), as the resolver uses.

Usage: ``python v3_side.py legacy_results.jsonl [trials=5000]``
"""

import json
import os
import sys

from geneweaver.db.query.membership import Thresholds
from geneweaver.db.tool_input import gene_symbols_by_geneset
from geneweaver.tools.mset import MSET, MSETInput
from geneweaver.tools.temporal.db import cursor as db_cursor
from geneweaver.tools.temporal.resolvers import resolve_input

BACKGROUNDS = {1: "GeneSymbolMusmusculusBG.txt", 2: "GeneSymbolHomosapiensBG.txt"}


def main() -> None:
    """Rerun each legacy pair through v3 with both universes and print the results."""
    legacy_results, trials = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    bg_dir = os.environ["MSET_LEGACY_BG_DIR"]
    with open(legacy_results) as handle:
        rows = [json.loads(line) for line in handle if '"legacy"' in line]
    for row in rows:
        first, second = row["pair"]
        with db_cursor() as cursor:
            members = gene_symbols_by_geneset(cursor, [first, second], Thresholds(mode="uploader"))
        list_1, list_2 = members[str(first)], members[str(second)]
        with open(os.path.join(bg_dir, BACKGROUNDS[row["sp_id"]])) as handle:
            legacy_background = handle.read().split()
        same_universe = MSET().run(
            MSETInput(
                group_1_genes=list_1,
                group_2_genes=list_2,
                group_1_background=legacy_background,
                group_2_background=legacy_background,
                number_of_samples=trials,
            )
        )
        # The worker's own path: the API sends a universe reference, the resolver expands it.
        resolved = resolve_input(
            "mset",
            {
                "tool": "mset",
                "input": {
                    "group_1_genes": list_1,
                    "group_2_genes": list_2,
                    "number_of_samples": trials,
                },
                "universe": {"geneset_ids": [first, second]},
            },
        )
        full_universe = MSET().run(MSETInput(**resolved))
        print(
            json.dumps(
                {
                    **row,
                    "v3_sizes": [len(set(list_1)), len(set(list_2))],
                    "v3_legacy_background": same_universe.mset_data,
                    "v3_full_universe": full_universe.mset_data,
                }
            )
        )


if __name__ == "__main__":
    main()
