"""Validate the ported BooleanAlgebra tool against the legacy CS_Boolean service on the DB.

BooleanAlgebra is a faithful refactor: the port (``geneweaver.tools.boolean_algebra``) is a
transcription of ``legacy/tools-worker/tools/TOOLBOX/CS_Boolean/service.py`` onto
``AbstractTool``, with DB access lifted out to the caller. This script proves the refactor by
running both on the *same* real homolog rows pulled from the local DB:

  - the homolog rows come from the legacy ``GET_HOMOLOGS_SQL`` (run verbatim under the legacy
    ``search_path``), so the DB wiring the port expects is exercised;
  - the legacy ``service.py`` set-logic functions are transcribed verbatim below and run
    through the same orchestration as the legacy ``BooleanAlgebra.mainexec``;
  - the port's ``BooleanAlgebra.run`` output is compared field-by-field against that legacy
    reference for union / intersection / except.

(The local ``extsrc.homology`` table is empty, so cross-species homolog merging is a no-op --
every gene keys to its own group -- but grouping, intersection, except, circle-code and the
per-species cluster aggregation are all still exercised over real membership data.)

Usage:
    uv run --extra sklearn --project packages/tools python \
        scripts/validation/validate_boolean_algebra.py
"""

# ruff: noqa: D103, UP018, RUF046, SIM113  (validation script; legacy CS_Boolean code transcribed verbatim)

from __future__ import annotations

import collections
import os
import sys
from typing import Any

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "tools", "src"))
from geneweaver.tools.boolean_algebra import BooleanAlgebra, BooleanAlgebraInput

DSN = "host=127.0.0.1 port=5433 dbname=geneweaver-dev user=geneweaver-dev password=localdev"
# Mouse + human gene sets -> >1 species, exercising the multi-species grouping branch.
GENESET_IDS = [514, 515, 648, 664, 32922, 32912, 32408, 270367, 270916, 366327]

# Legacy GET_HOMOLOGS_SQL, verbatim from CS_Boolean/service.py (relies on the search_path).
GET_HOMOLOGS_SQL = """SELECT hom.hom_source_id, g.ode_gene_id, g.ode_ref_id, g.sp_id, gv.gs_id, gs.gs_abbreviation
                            FROM gene g NATURAL JOIN geneset_value gv NATURAL
                            JOIN geneset gs LEFT JOIN
                              (SELECT ode_gene_id, hom_source_id
                                    FROM homology
                                    WHERE hom_source_name = 'Homologene'
                                    AND hom_source_id IN
                                      (SELECT hom_source_id
                                          FROM homology h, geneset_value gv2
                                          WHERE h.ode_gene_id = gv2.ode_gene_id
                                          AND gv2.gs_id IN {0}
                                          AND gv2.gsv_in_threshold
                                      )
                                    AND sp_id IN ({1})
                              ) hom
                              ON g.ode_gene_id = hom.ode_gene_id
                            WHERE gv.gs_id IN {0}
                            AND gv.gsv_in_threshold
                            AND g.gdb_id = 7
                            AND g.ode_pref = TRUE
                              ORDER BY hom.hom_source_id, gv.gs_id"""


# --- legacy CS_Boolean/service.py set logic, transcribed verbatim --------------------------


def legacy_group_homologs(homologs, species_ids):
    bool_results: dict[Any, list] = {}
    for homolog in homologs:
        key = homolog[0]
        if len(species_ids) == 1:
            key = homolog[1]
        elif not homolog[0]:
            key = -1 * homolog[1]
        current_val = bool_results.get(key, [])
        current_val.append(homolog[1:5])
        bool_results[key] = current_val
    for key in bool_results:
        group = bool_results[key]
        seen: set = set()
        deduped = []
        for item in group:
            t = tuple(item)
            if t not in seen:
                seen.add(t)
                deduped.append(list(t))
        bool_results[key] = deduped
    return {i[0]: i[1] for i in sorted(bool_results.items(), key=lambda t: len(t[1][0]))}


def legacy_intersect(bool_results, at_least=2):
    intersect_results = {k: v for k, v in bool_results.items() if len(v) >= int(at_least)}
    for key in intersect_results:
        group = intersect_results[key]
        if not group:
            continue
        seen: set = set()
        deduped = []
        for item in group:
            if item[3] not in seen:
                seen.add(item[3])
                deduped.append(item)
        intersect_results[key] = deduped
    intersection_sizes: dict = collections.defaultdict(dict)
    for k, v in intersect_results.items():
        intersection_sizes[len(v)][k] = v
    return dict(intersection_sizes)


def legacy_bool_except(bool_results):
    bool_except: dict = collections.defaultdict(dict)
    intersects = {k: v for k, v in bool_results.items() if len(v) >= int(2)}
    except_results = {k: v for k, v in bool_results.items() if k not in intersects}
    compare: dict = collections.defaultdict(list)
    for key, value in except_results.items():
        compare[value[0][3]].append(key)
    i = 0
    for _key, value in compare.items():
        for j in range(len(value)):
            for k, v in except_results.items():
                if int(k) == int(value[j]):
                    bool_except[i][value[j]] = v
        i += 1
    return dict(bool_except)


def legacy_cluster_genes(homolog_data, species_ids):
    genes = {sp: {"unique": [], "intersection": [], "species": []} for sp in species_ids}
    for homolog in homolog_data:
        genes[homolog[3]]["species"].append(homolog[0])
    all_other: list = []
    this_sp: list = []
    for outer in species_ids:
        for inner in species_ids:
            if outer != inner:
                all_other.extend(genes[inner]["species"])
            else:
                this_sp.extend(genes[inner]["species"])
        genes[outer]["unique"].extend(list(set(this_sp) - set(all_other)))
        del all_other[:]
        del this_sp[:]
    inter: list = []
    for i in range(len(species_ids)):
        for j in range(len(genes[species_ids[i]]["species"])):
            for k in range(len(species_ids)):
                if i != k and genes[species_ids[i]]["species"][j] in genes[species_ids[k]]["species"]:
                    inter.append(genes[species_ids[i]]["species"][j])
        genes[species_ids[i]]["intersection"].extend(inter)
        del inter[:]
    return genes


def legacy_create_circle_code(bool_results):
    gps: dict = collections.defaultdict(list)
    for key in bool_results:
        for k in bool_results[key]:
            gps[key].append(k[3])
    return dict(gps)


def legacy_reference(homolog_data, species_ids, relation, at_least):
    """Reproduce the legacy BooleanAlgebra.mainexec orchestration for one relation."""
    bool_results = legacy_group_homologs(homolog_data, species_ids)
    result_geneset_ids = list({item[4] for item in homolog_data})
    circle = None
    if 1 <= len(result_geneset_ids) <= 10:
        circle = legacy_create_circle_code(bool_results)
    intersect_results = None
    except_results = None
    if relation != "union":
        intersect_results = legacy_intersect(bool_results, at_least)
        if relation == "except":
            except_results = legacy_bool_except(bool_results)
    cluster = legacy_cluster_genes(homolog_data, species_ids)
    return {
        "bool_results": bool_results,
        "circle_groups": circle,
        "intersect_results": intersect_results,
        "bool_except": except_results,
        "bool_cluster": cluster,
    }


def species_in_genesets(cur, geneset_ids):
    """Legacy get_species_in_genesets: distinct sp_id over the gene sets."""
    sp: set = set()
    for g in geneset_ids:
        cur.execute("SELECT DISTINCT sp_id FROM production.geneset WHERE gs_id=%s", (g,))
        sp.update(int(r[0]) for r in cur.fetchall())
    return list(sp)


def load_homologs(cur, geneset_ids, species_ids):
    sql = GET_HOMOLOGS_SQL.format(tuple(geneset_ids), ",".join(str(s) for s in species_ids))
    cur.execute(sql)
    # Return as lists so port and legacy operate on identical row objects.
    return [list(r) for r in cur.fetchall()]


def norm_cluster(cluster):
    """Order-independent view of bool_cluster (lists may contain None hom ids)."""
    return {
        sp: {k: collections.Counter(v) for k, v in groups.items()}
        for sp, groups in cluster.items()
    }


def main():
    """Pull real homolog rows and compare the port vs the legacy reference per relation."""
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("SET search_path TO production,extsrc,odestatic;")
        sp_ids = species_in_genesets(cur, GENESET_IDS)
        homolog_data = load_homologs(cur, GENESET_IDS, sp_ids)
        conn.rollback()

    n_gs = len({r[4] for r in homolog_data})
    print(
        f"graph: {len(homolog_data)} homolog rows over {n_gs} gene sets, "
        f"{len(sp_ids)} species {sorted(sp_ids)}  (homology table empty -> no homolog merge)\n"
    )

    tool = BooleanAlgebra()
    all_ok = True
    for relation in ("union", "intersection", "except"):
        # port operates on copies so the legacy reference sees pristine rows
        port = tool.run(
            BooleanAlgebraInput(
                relation=relation,
                at_least=2,
                geneset_ids=GENESET_IDS,
                species_ids=sp_ids,
                homolog_data=[list(r) for r in homolog_data],
            )
        )
        ref = legacy_reference([list(r) for r in homolog_data], sp_ids, relation, 2)

        checks = {
            "bool_results": port.bool_results == ref["bool_results"],
            "circle_groups": port.circle_groups == ref["circle_groups"],
            "intersect_results": port.intersect_results == ref["intersect_results"],
            "bool_except": port.bool_except == ref["bool_except"],
            "bool_cluster": norm_cluster(port.bool_cluster) == norm_cluster(ref["bool_cluster"]),
        }
        ok = all(checks.values())
        all_ok &= ok
        ng = len(port.bool_results)
        ni = None if port.intersect_results is None else sum(
            len(v) for v in port.intersect_results.values()
        )
        bad = [k for k, v in checks.items() if not v]
        print(
            f"  {relation:13s} groups={ng:<4d} intersect_groups={ni!s:<5} "
            f"{'OK' if ok else 'MISMATCH ' + ','.join(bad)}"
        )

    print("\nRESULT:", "ALL RELATIONS MATCH ✓" if all_ok else "MISMATCHES FOUND ✗")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
