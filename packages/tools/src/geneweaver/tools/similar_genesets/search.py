"""Running Similar gene sets against the database and naming what it finds.

A database search, like ABBA, so it takes a connection and needs the `db` extra. The Temporal
activity runs it on the tool worker; the API runs the same function in-process where
AsyncTask is not configured.
"""

from typing import TYPE_CHECKING

from geneweaver.tools.similar_genesets.schema import SimilarGenesetsInput, SimilarGenesetsOutput

if TYPE_CHECKING:  # pragma: no cover - typing only
    from psycopg import Connection

#: Bounds the one query. It takes about two minutes on dev for a gene set sharing genes
#: with 86,000 others; the workflow itself allows 30.
DEFAULT_STATEMENT_TIMEOUT_SECONDS = 600

#: For this transaction only: ~105 s on dev at this, against ~120-155 s at the default.
WORK_MEM = "256MB"


def search(
    connection: "Connection",
    request: SimilarGenesetsInput,
    user_id: int,
    statement_timeout_seconds: int = DEFAULT_STATEMENT_TIMEOUT_SECONDS,
) -> SimilarGenesetsOutput:
    """Find the gene sets most like ``request.geneset_id``, in one read-only transaction.

    :param user_id: Whose private gene sets may be listed; 0 for public gene sets only.
        The caller has already checked that this user may read the viewed gene set.
    """
    from geneweaver.db.query.membership import Thresholds
    from geneweaver.db.query.similar_genesets import similar_genesets
    from psycopg.rows import tuple_row

    query, params = similar_genesets(
        request.geneset_id,
        user_id,
        Thresholds(**request.membership_kwargs()),
        request.limit,
    )
    with connection.transaction(), connection.cursor(row_factory=tuple_row) as rows:
        rows.execute(
            "SELECT set_config('statement_timeout', %s, true)",
            (f"{statement_timeout_seconds}s",),
        )
        # Its de-duplication of every candidate's genes spills to disk at the default 4 MB.
        rows.execute("SELECT set_config('work_mem', %s, true)", (WORK_MEM,))
        rows.execute("SELECT sp_id, sp_name FROM odestatic.species ORDER BY sp_id")
        species = {key: name for key, name in rows.fetchall() if name}
        rows.execute("SELECT cur_id, cur_name FROM odestatic.curation_levels ORDER BY cur_id")
        tiers = dict(rows.fetchall())
        rows.execute(query, params)
        found = rows.fetchall()
        if not found:
            rows.execute(*viewed_size(request))
            viewed = rows.fetchone()[0]
    return shape(found, request, species, tiers, viewed=None if found else viewed)


def viewed_size(request: SimilarGenesetsInput) -> tuple:
    """The viewed gene set's size, for a run that found nothing to report it from."""
    from geneweaver.db.query.membership import Thresholds, membership_filter
    from psycopg.sql import SQL

    keep, params = membership_filter(Thresholds(**request.membership_kwargs()), gv="gv", gs="gs")
    return (
        SQL(
            "SELECT count(DISTINCT CASE WHEN h.hom_id IS NULL THEN 'g' || gv.ode_gene_id "
            "ELSE 'h' || h.hom_id END) FROM extsrc.geneset_value gv "
            "JOIN production.geneset gs ON gs.gs_id = gv.gs_id "
            "LEFT JOIN extsrc.homology h ON h.ode_gene_id = gv.ode_gene_id "
            "WHERE gv.gs_id = %(geneset_id)s AND {keep}"
        ).format(keep=keep),
        {"geneset_id": request.geneset_id, **params},
    )


def shape(
    found: list[tuple],
    request: SimilarGenesetsInput,
    species: dict[int, str],
    tiers: dict[int, str],
    viewed: int | None = None,
) -> SimilarGenesetsOutput:
    """Name the query's positional rows; the UI renders from these fields."""
    first = found[0] if found else None
    return SimilarGenesetsOutput(
        geneset_id=request.geneset_id,
        genes=first[9] if first else (viewed or 0),
        thresholds=request.threshold_choice(),
        compared=first[10] if first else 0,
        genesets=[
            {
                "gs_id": gs_id,
                "name": name,
                "abbreviation": abbreviation,
                "species_id": species_id,
                "tier": tier,
                "attribution": attribution,
                "genes": genes,
                "shared": shared,
                "jaccard": jaccard,
            }
            for gs_id, name, abbreviation, species_id, tier, attribution, genes, shared, jaccard, *_ in found
        ],
        species=species,
        tiers=tiers,
    )
