"""Boolean Algebra tool, reimplemented on the AbstractTool framework.

Ported faithfully from the legacy Celery worker:
  - legacy/tools-worker/tools/BooleanAlgebra.py (orchestration)
  - legacy/tools-worker/tools/TOOLBOX/CS_Boolean/service.py (the set logic)

The legacy tool fetched homologs/species from the GeneWeaver DB inside the task. Here
that DB access is the caller's responsibility (passed in via BooleanAlgebraInput), so
this tool is pure: same set-algebra, no DB or Celery coupling.
"""

from __future__ import annotations

import collections
from typing import Any

from geneweaver.tools.framework.abstract import AbstractTool

from .schema import BooleanAlgebraInput, BooleanAlgebraOutput


def group_homologs(
    homologs: list[list[Any]], species_ids: list[int]
) -> dict[int, list[list[Any]]]:
    """Group homolog rows by homology key (multi-species) or gene id (single species)."""
    bool_results: dict[int, list[list[Any]]] = {}
    for homolog in homologs:
        key = homolog[0]
        if len(species_ids) == 1:
            key = homolog[1]
        elif not homolog[0]:
            key = -1 * homolog[1]
        bool_results.setdefault(key, []).append(list(homolog[1:5]))

    # Deduplicate each group while preserving order.
    for key, group in bool_results.items():
        seen: set[tuple] = set()
        deduped: list[list[Any]] = []
        for item in group:
            t = tuple(item)
            if t not in seen:
                seen.add(t)
                deduped.append(list(t))
        bool_results[key] = deduped

    return dict(sorted(bool_results.items(), key=lambda t: len(t[1][0])))


def intersect(
    bool_results: dict[int, list[list[Any]]], at_least: int = 2
) -> dict[int, dict[int, list[list[Any]]]]:
    """Keep groups with >= at_least rows, dedup by gs_id, bucket by intersection size."""
    intersect_results = {k: v for k, v in bool_results.items() if len(v) >= int(at_least)}
    for key, group in intersect_results.items():
        if not group:
            continue
        seen: set = set()
        deduped: list[list[Any]] = []
        for item in group:
            if item[3] not in seen:
                seen.add(item[3])
                deduped.append(item)
        intersect_results[key] = deduped

    intersection_sizes: dict[int, dict[int, list[list[Any]]]] = collections.defaultdict(dict)
    for k, v in intersect_results.items():
        intersection_sizes[len(v)][k] = v
    return dict(intersection_sizes)


def bool_except(bool_results: dict[int, list[list[Any]]]) -> dict[int, dict[int, list[list[Any]]]]:
    """Groups that appear in only one gene set (the complement of the intersections)."""
    result: dict[int, dict[int, list[list[Any]]]] = collections.defaultdict(dict)
    intersects = {k: v for k, v in bool_results.items() if len(v) >= 2}
    except_results = {k: v for k, v in bool_results.items() if k not in intersects}

    compare: dict[Any, list[int]] = collections.defaultdict(list)
    for key, value in except_results.items():
        compare[value[0][3]].append(key)

    for i, value in enumerate(compare.values()):
        for j in range(len(value)):
            for k, v in except_results.items():
                if int(k) == int(value[j]):
                    result[i][value[j]] = v
    return dict(result)


def cluster_genes(
    homolog_data: list[list[Any]], species_ids: list[int]
) -> dict[int, dict[str, list[Any]]]:
    """Per-species unique / intersection / all gene clustering (for the d3 graph)."""
    genes: dict[int, dict[str, list[Any]]] = {
        sp: {"unique": [], "intersection": [], "species": []} for sp in species_ids
    }
    for homolog in homolog_data:
        genes[homolog[3]]["species"].append(homolog[0])

    all_other: list[Any] = []
    this_sp: list[Any] = []
    for outer in species_ids:
        for inner in species_ids:
            if outer != inner:
                all_other.extend(genes[inner]["species"])
            else:
                this_sp.extend(genes[inner]["species"])
        genes[outer]["unique"].extend(list(set(this_sp) - set(all_other)))
        all_other.clear()
        this_sp.clear()

    inter: list[Any] = []
    for i in range(len(species_ids)):
        for j in range(len(genes[species_ids[i]]["species"])):
            for k in range(len(species_ids)):
                if (
                    i != k
                    and genes[species_ids[i]]["species"][j] in genes[species_ids[k]]["species"]
                ):
                    inter.append(genes[species_ids[i]]["species"][j])
        genes[species_ids[i]]["intersection"].extend(inter)
        inter.clear()
    return genes


def create_circle_code(bool_results: dict[int, list[list[Any]]]) -> dict[int, list[Any]]:
    """Map each group key to the list of gs_ids it spans (for venn circles)."""
    gps: dict[int, list[Any]] = collections.defaultdict(list)
    for key, rows in bool_results.items():
        for row in rows:
            gps[key].append(row[3])
    return dict(gps)


class BooleanAlgebra(AbstractTool):
    """Union / Intersection / Except over the homologs of a set of gene sets."""

    @property
    def tool_input(self) -> type[BooleanAlgebraInput]:
        """Input schema for the tool."""
        return BooleanAlgebraInput

    @property
    def tool_output(self) -> type[BooleanAlgebraOutput]:
        """Output schema for the tool."""
        return BooleanAlgebraOutput

    def run(self, tool_input: BooleanAlgebraInput) -> BooleanAlgebraOutput:
        """Run the Boolean Algebra set operations over the provided homolog data."""
        relation = tool_input.relation.lower()
        homologs = tool_input.homolog_data
        species_ids = tool_input.species_ids

        bool_results = group_homologs(homologs, species_ids)
        result_geneset_ids = list({row[4] for row in homologs})

        circle_groups = None
        if 1 <= len(result_geneset_ids) <= 10:
            circle_groups = create_circle_code(bool_results)

        intersect_results = None
        except_results = None
        if relation != "union":
            intersect_results = intersect(bool_results, tool_input.at_least)
            if relation == "except":
                except_results = bool_except(bool_results)

        return BooleanAlgebraOutput(
            relation=relation.title(),
            at_least=tool_input.at_least,
            num_genesets=len(tool_input.geneset_ids),
            num_species=len(species_ids),
            geneset_ids=result_geneset_ids,
            species_ids=species_ids,
            bool_results=bool_results,
            circle_groups=circle_groups,
            intersect_results=intersect_results,
            bool_except=except_results,
            bool_cluster=cluster_genes(homologs, species_ids),
        )
