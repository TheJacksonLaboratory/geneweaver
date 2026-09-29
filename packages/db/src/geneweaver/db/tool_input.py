"""Resolve database state into the inputs the ported analysis tools expect.

The tools in ``geneweaver-tools`` are pure: each takes a fully-built ``ToolInput`` and
touches no database. Something has to assemble that input, and this module is where those
resolvers live (G3-798). Only ABBA had one before -- ``geneweaver.db.abba``.

Keeping the resolvers here rather than in the API means the same input can be built by
whatever ends up executing the tool, in-process today or AsyncTask later.

Access control is deliberately *not* done here. These functions answer "what is in this
gene set"; deciding whether the caller may see it belongs to the service layer, which knows
about users. Callers must gate first.
"""

from typing import Any

from geneweaver.core.enum import GeneIdentifier
from geneweaver.db.gene import symbols_by_geneset_id
from psycopg import Cursor


def _symbol(row: Any) -> str:
    """Read the gene symbol from a row under either row factory.

    The API's connection pool uses ``dict_row`` (``dependencies.py``), while parts of
    ``packages/db`` and its tests use tuple rows.
    """
    if isinstance(row, dict):
        return row["ode_ref_id"]
    return row[0]


def gene_symbols_by_geneset(cursor: Cursor, geneset_ids: list[int]) -> dict[str, list[str]]:
    """Map each gene set id to its preferred gene symbols.

    This is the input shape shared by the membership-based tools -- UpSet, DBSCAN and
    PhenomeMap all want "the genes in each of these sets".

    Uses the same filter the legacy tools did (``gdb_id = 7``, ``ode_pref = 't'``), so a
    set resolves to the same symbols the legacy worker would have received.

    :param cursor: The database cursor.
    :param geneset_ids: The gene sets to resolve, in the caller's order.
    :return: ``{geneset_id_as_str: [symbol, ...]}``, preserving input order.
    """
    memberships: dict[str, list[str]] = {}
    for geneset_id in geneset_ids:
        rows = symbols_by_geneset_id(cursor, geneset_id)
        memberships[str(geneset_id)] = [_symbol(row) for row in rows]
    return memberships


def species_by_geneset(cursor: Cursor, geneset_ids: list[int]) -> dict[int, int]:
    """Map each gene set id to its species id.

    MSET compares two gene sets against a shared gene universe, which is per species, so
    the caller has to know the species before it can resolve one.

    :param cursor: The database cursor.
    :param geneset_ids: The gene sets to look up.
    :return: ``{geneset_id: sp_id}``, omitting ids that do not exist.
    """
    if not geneset_ids:
        return {}
    cursor.execute(
        """
        SELECT gs_id, sp_id
        FROM production.geneset
        WHERE gs_id = ANY(%(geneset_ids)s);
        """,
        {"geneset_ids": list(geneset_ids)},
    )
    rows = cursor.fetchall()
    if rows and isinstance(rows[0], dict):
        return {row["gs_id"]: row["sp_id"] for row in rows}
    return {row[0]: row[1] for row in rows}


def gene_universe(
    cursor: Cursor,
    species_id: int,
    gene_id_type: int = int(GeneIdentifier.GENE_SYMBOL),
) -> list[str]:
    """Every gene identifier GeneWeaver knows for a species -- MSET's background.

    This is the **full gene space**, not the genes appearing in curated gene sets. Legacy
    used the latter, precomputed into ~600 ``*BG.txt`` files, which meant a gene unique to a
    Tier-IV set sat outside its own background and MSET refused the run (GWC-51 / G3-783);
    the files also went stale on every gene reload (GWC-45 / G3-766). Resolving here removes
    both, and the regeneration job and per-environment storage with them (G3-784).

    ``gene_id_type`` defaults to gene symbols because that is the space
    :func:`gene_symbols_by_geneset` returns the member lists in, and MSET requires each list
    to be a subset of its background. Legacy keyed the background file off the *gene set's*
    ``gene_id_type`` while fetching members as symbols, so any set whose type was not Gene
    Symbol produced a background the members could not possibly belong to -- which is part of
    why 450 of those 602 files were empty. Pass something else only alongside member lists
    resolved in that same space.

    :param cursor: The database cursor.
    :param species_id: The species whose gene space to return.
    :param gene_id_type: ``gdb_id`` of the identifier space; gene symbols by default.
    :return: Sorted, de-duplicated identifiers.
    """
    cursor.execute(
        """
        SELECT DISTINCT ode_ref_id
        FROM extsrc.gene
        WHERE sp_id = %(species_id)s
          AND gdb_id = %(gene_id_type)s
          AND ode_pref = 't'
        ORDER BY ode_ref_id;
        """,
        {"species_id": species_id, "gene_id_type": gene_id_type},
    )
    return [_symbol(row) for row in cursor.fetchall()]
