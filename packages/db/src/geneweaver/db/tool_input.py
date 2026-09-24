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
