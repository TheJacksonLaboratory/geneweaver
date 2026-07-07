"""Gene-set Jaccard similarity (the "similar gene sets" computation).

Replaces the legacy ``production.calculate_jaccard`` stored procedure (invoked by the
legacy ``SimilarGenesets`` Celery task) with a versioned, testable db-layer function.

The computation is one gene set vs. every other gene set over the whole database, so the
heavy set work deliberately stays in Postgres; this function orchestrates the steps and
returns the number of cached pairs. The caller owns the transaction/commit and the async
execution (it can take minutes on the full database).
"""

from geneweaver.db.query import geneset_jaccard as jaccard_query
from geneweaver.db.query.geneset_jaccard import DEFAULT_MIN_JACCARD
from psycopg import Cursor


def calculate_jaccard(cursor: Cursor, gs_id: int, min_jaccard: float = DEFAULT_MIN_JACCARD) -> int:
    """Compute and cache Jaccard similarity between a gene set and all others.

    Faithful port of ``production.calculate_jaccard(bigint)``: set the start time, clear
    any stale cache, insert the forward and reverse Jaccard coefficients (>= ``min_jaccard``)
    into ``geneset_jaccard``, set the completed time, and return the number of cached pairs.

    :param cursor: a database cursor (search_path must include production, extsrc).
    :param gs_id: the source gene set id.
    :param min_jaccard: only cache pairs with a coefficient at least this large.
    :return: the number of cached Jaccard pairs involving this gene set.
    """
    cursor.execute(*jaccard_query.set_jaccard_started(gs_id))
    cursor.execute(*jaccard_query.clear_jaccard_cache(gs_id))
    cursor.execute(*jaccard_query.insert_jaccards(gs_id, min_jaccard, reverse=False))
    cursor.execute(*jaccard_query.insert_jaccards(gs_id, min_jaccard, reverse=True))
    cursor.execute(*jaccard_query.set_jaccard_completed(gs_id))
    cursor.execute(*jaccard_query.count_jaccards(gs_id))
    return cursor.fetchone()[0]


def clear_jaccard(cursor: Cursor, gs_id: int) -> None:
    """Clear the cached Jaccard pairs and timestamps for a gene set (e.g. before a refresh)."""
    cursor.execute(*jaccard_query.clear_jaccard_times(gs_id))
    cursor.execute(*jaccard_query.clear_jaccard_cache(gs_id))
