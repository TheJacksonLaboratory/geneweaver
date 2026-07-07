"""Query builders for gene-set Jaccard similarity.

Ports the legacy ``production.calculate_jaccard(bigint)`` stored procedure into versioned,
parameterised queries. The heavy set work still runs in Postgres (it is a one-vs-all
comparison over every gene set), but the SQL now lives in code: testable and reviewable.

Table names are unqualified to follow this package's convention (the connection
search_path provides ``production`` and ``extsrc``).

Note on fidelity: the legacy SQL takes documented accuracy shortcuts for speed
("all genes in other species have a homolog in the source species; all homologs are
one-to-one"). That behaviour is preserved here unchanged.
"""

from psycopg.sql import SQL

# Default minimum Jaccard coefficient to cache (the legacy proc hard-coded 0.005).
DEFAULT_MIN_JACCARD = 0.005
# Pattern for deprecated gene sets, passed as a parameter to avoid `%` escaping.
_DEPRECATED_PATTERN = "de%"


def set_jaccard_started(gs_id: int) -> tuple[SQL, dict]:
    """Mark the Jaccard calculation as started for a gene set."""
    return (
        SQL("UPDATE geneset_info SET gsi_jac_started = NOW() WHERE gs_id = %(gs_id)s;"),
        {"gs_id": gs_id},
    )


def set_jaccard_completed(gs_id: int) -> tuple[SQL, dict]:
    """Mark the Jaccard calculation as completed for a gene set."""
    return (
        SQL("UPDATE geneset_info SET gsi_jac_completed = NOW() WHERE gs_id = %(gs_id)s;"),
        {"gs_id": gs_id},
    )


def clear_jaccard_times(gs_id: int) -> tuple[SQL, dict]:
    """Clear the Jaccard started/completed timestamps for a gene set."""
    return (
        SQL(
            "UPDATE geneset_info SET gsi_jac_started = NULL, gsi_jac_completed = NULL "
            "WHERE gs_id = %(gs_id)s;"
        ),
        {"gs_id": gs_id},
    )


def clear_jaccard_cache(gs_id: int) -> tuple[SQL, dict]:
    """Delete cached Jaccard pairs involving a gene set (avoids duplicate-key errors)."""
    return (
        SQL(
            "DELETE FROM geneset_jaccard WHERE gs_id_left = %(gs_id)s OR gs_id_right = %(gs_id)s;"
        ),
        {"gs_id": gs_id},
    )


def insert_jaccards(
    gs_id: int, min_jaccard: float = DEFAULT_MIN_JACCARD, *, reverse: bool = False
) -> tuple[SQL, dict]:
    """Compute and cache Jaccard coefficients between ``gs_id`` and other gene sets.

    The legacy proc runs this twice: ``reverse=False`` against gene sets with a larger id
    (cached as ``(gs_id, other)``) and ``reverse=True`` against smaller ids (cached as
    ``(other, gs_id)``), so each unordered pair is stored once.

    :param gs_id: the source gene set id.
    :param min_jaccard: only cache pairs with a coefficient at least this large.
    :param reverse: see above.
    :return: a query (and params) that can be executed on a cursor.
    """
    comparison = "<" if reverse else ">"
    left, right = ("gs.gs_id", "%(gs_id)s") if reverse else ("%(gs_id)s", "gs.gs_id")
    jac_expr = (
        "CAST(x.int_count AS numeric) / (CAST(x.gs_count AS numeric) "
        "+ (SELECT gs_count FROM geneset WHERE gs_id = %(gs_id)s) - CAST(x.int_count AS numeric))"
    )
    query = SQL(
        f"""
        INSERT INTO geneset_jaccard (gs_id_left, gs_id_right, jac_value)
        SELECT {left}, {right}, {jac_expr} AS jac
        FROM geneset gs,
             (SELECT gs_id, gs_count, count(ode_gene_id) AS int_count
                FROM geneset NATURAL JOIN geneset_value
               WHERE gs_id {comparison} %(gs_id)s AND gsv_in_threshold
                 AND ode_gene_id IN (
                     (SELECT a.ode_gene_id
                        FROM homology a, homology b
                       WHERE a.hom_id = b.hom_id
                         AND b.ode_gene_id IN (
                             SELECT ode_gene_id FROM geneset_value
                              WHERE gsv_in_threshold AND gs_id = %(gs_id)s))
                     UNION
                     (SELECT ode_gene_id FROM geneset_value
                       WHERE gsv_in_threshold AND gs_id = %(gs_id)s)
                 )
               GROUP BY gs_id, gs_count) x
        WHERE gs.gs_status NOT LIKE %(deprecated)s
          AND x.gs_id = gs.gs_id
          AND {jac_expr} >= %(min_jaccard)s;
        """
    )
    return query, {
        "gs_id": gs_id,
        "min_jaccard": min_jaccard,
        "deprecated": _DEPRECATED_PATTERN,
    }


def count_jaccards(gs_id: int) -> tuple[SQL, dict]:
    """Count cached Jaccard pairs involving a gene set."""
    return (
        SQL(
            "SELECT count(*) FROM geneset_jaccard "
            "WHERE gs_id_left = %(gs_id)s OR gs_id_right = %(gs_id)s;"
        ),
        {"gs_id": gs_id},
    )
