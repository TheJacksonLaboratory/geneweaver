"""Legacy half of the MSET comparison (G3-784): run inside a legacy tools worker pod.

Samples curated (Tier I-III), gene-symbol-typed, same-species gene-set pairs, resolves each
list with legacy's own query (``geneweaverdb.get_genesymbols_by_gs_id``) and runs ``MSETcpp``
exactly as ``tools-worker/tools/MSET.py`` does, against the background file legacy reads in
that environment. Prints one JSON line per pair, which ``v3_side.py`` then reruns.

Read-only on the database. Temp files live in one directory, removed at the end.

Environment (all optional; the defaults are the legacy worker image's):

* ``LEGACY_TOOLS_DIR`` -- the worker's code, default ``/app/tools-worker``.
* ``GW_MSET_BG_DIR`` / ``APPLICATION_RESULTS`` -- where legacy reads backgrounds, resolved
  the way ``MSET.py`` resolves them, falling back to the in-image ``backgroundFiles``.

Usage: ``python legacy_side.py [trials=5000] [pairs_per_species=6] [seed=784]``
"""

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile

TOOLS_DIR = os.environ.get("LEGACY_TOOLS_DIR", "/app/tools-worker")
sys.path.insert(0, TOOLS_DIR)

import psycopg2  # noqa: E402
from tools import config  # noqa: E402

MSET_DIR = os.path.join(TOOLS_DIR, "tools", "TOOLBOX", "CS_Mset")
BINARY = os.path.join(MSET_DIR, "MSETcpp")
#: The species compared, and legacy's background file name for gene-symbol sets of each.
SPECIES = {1: "GeneSymbolMusmusculusBG.txt", 2: "GeneSymbolHomosapiensBG.txt"}

TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
PER_SPECIES = int(sys.argv[2]) if len(sys.argv) > 2 else 6
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 784


def background_dir() -> str:
    """Where legacy reads backgrounds: ``MSET.py``'s own order of preference."""
    results = os.environ.get("APPLICATION_RESULTS")
    preferred = os.environ.get("GW_MSET_BG_DIR") or (
        os.path.join(results, "mset_backgrounds") if results else None
    )
    if preferred and os.path.isdir(preferred):
        return preferred
    return os.path.join(MSET_DIR, "backgroundFiles")


def legacy_genes(cursor, gs_id: int) -> list[str]:
    """``get_genesymbols_by_gs_id``, verbatim."""
    cursor.execute(
        "select g.ode_ref_id from gene g, geneset_value gv where gv.gs_id= %s and "
        "gv.ode_gene_id=g.ode_gene_id and gv.gsv_in_threshold and g.gdb_id=7 and ode_pref='t';",
        (gs_id,),
    )
    return [row[0] for row in cursor.fetchall()]


def main() -> None:
    """Run legacy MSET on sampled pairs and print the results."""
    conn = psycopg2.connect(
        database=config.get("db", "database"),
        user=config.get("db", "user"),
        password=config.get("db", "password"),
        host=config.get("db", "host"),
        port=config.get("db", "port"),
    )
    conn.set_session(readonly=True)
    cursor = conn.cursor()
    bg_dir = background_dir()
    rng = random.Random(SEED)
    work = tempfile.mkdtemp(prefix="mset_vs_legacy_")
    try:
        for sp_id, bg_name in SPECIES.items():
            bg_path = os.path.join(bg_dir, bg_name)
            with open(bg_path) as handle:
                background = set(handle.read().split())
            cursor.execute(
                "SELECT gs_id FROM production.geneset WHERE sp_id = %s AND cur_id IN (1, 2, 3) "
                "AND gs_status NOT LIKE 'de%%' AND gs_gene_id_type <= 0 "
                "AND gs_count BETWEEN 100 AND 800 ORDER BY gs_id",
                (sp_id,),
            )
            candidates = [row[0] for row in cursor.fetchall()]
            kept = 0
            for _ in range(400):
                if kept >= PER_SPECIES:
                    break
                first, second = rng.sample(candidates, 2)
                list_1, list_2 = legacy_genes(cursor, first), legacy_genes(cursor, second)
                overlap = len(set(list_1) & set(list_2))
                # Legacy refuses a list outside its background, so only runnable pairs are
                # comparable; an overlap of at least two keeps p away from the trivial 1.0.
                if overlap < 2 or not (set(list_1) | set(list_2)) <= background:
                    continue
                paths = []
                for index, genes in enumerate((list_1, list_2), start=1):
                    path = os.path.join(work, f"list_{index}.txt")
                    with open(path, "w") as handle:
                        handle.write("\n".join(genes) + "\n")
                    paths.append(path)
                command = [BINARY, str(TRIALS), paths[0], bg_path, paths[1], bg_path, "-O"]
                proc = subprocess.run(command, capture_output=True, text=True, cwd=work)
                if proc.returncode != 0:
                    print(json.dumps({"pair": [first, second], "error": proc.stderr[:300]}))
                    continue
                with open(os.path.join(work, "mset_output.tsv")) as handle:
                    data = {
                        row[0]: row[1].strip() for row in (line.split("\t") for line in handle)
                    }
                print(
                    json.dumps(
                        {
                            "pair": [first, second],
                            "sp_id": sp_id,
                            "legacy_sizes": [len(list_1), len(list_2)],
                            "legacy_background": bg_path,
                            "legacy": data,
                        }
                    )
                )
                kept += 1
    finally:
        shutil.rmtree(work, ignore_errors=True)
        conn.close()


if __name__ == "__main__":
    main()
