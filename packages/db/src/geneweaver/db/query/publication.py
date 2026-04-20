"""Generate SQL queries for publications."""

from collections.abc import Iterable

from geneweaver.db.query.const import (
    PUB_INSERT_COLS,
    PUB_INSERT_VALS,
    PUB_QUERY,
    PUB_TSVECTOR,
)
from geneweaver.db.query.search import utils
from geneweaver.db.query.utils import (
    ParamDict,
    SQLList,
    construct_filters,
)
from geneweaver.db.utils import limit_and_offset
from psycopg import rows
from psycopg.sql import SQL, Composed


def get(
    pub_id: int | None = None,
    authors: str | None = None,
    title: str | None = None,
    abstract: str | None = None,
    journal: str | None = None,
    volume: str | None = None,
    pages: str | None = None,
    month: str | None = None,
    year: str | None = None,
    pubmed: str | None = None,
    search_text: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> tuple[Composed, dict]:
    """Get publications by some criteria.

    :param pub_id: Show only results with this publication id
    :param authors: Show only results with these authors
    :param title: Show only results with this title
    :param abstract: Show only results with this abstract
    :param journal: Show only results with this journal
    :param volume: Show only results with volume
    :param pages: Show only results with these pages
    :param month: Show only results with this publication month
    :param year: Show only results with publication year
    :param pubmed: Show only results with pubmed id
    :param search_text: Show only results that match this search text (using PostgreSQL
                        full-text search).
    :param limit: Limit the number of results.
    :param offset: Offset the results.

    """
    params = {}
    filtering = []
    query = PUB_QUERY

    filtering, params = search(filtering, params, search_text)

    filtering, params = construct_filters(
        filtering,
        params,
        {
            "pub_id": pub_id,
            "pub_authors": authors,
            "pub_title": title,
            "pub_abstract": abstract,
            "pub_journal": journal,
            "pub_volume": volume,
            "pub_pages": pages,
            "pub_month": month,
            "pub_year": year,
            "pub_pubmed": pubmed,
        },
    )

    if len(filtering) > 0:
        query += SQL("WHERE") + SQL("AND").join(filtering)

    query = limit_and_offset(query, limit, offset).join(" ")

    return query, params


def by_id(pub_id: int) -> rows.Row | None:
    """Create a psycopg query to get a publication by ID.

    :param pub_id: The publication ID (geneweaver internal) to search for.

    :return: A query (and params) that can be executed on a cursor.
    """
    query = (PUB_QUERY + SQL("WHERE pub_id = %(pub_id)s")).join(" ")
    params = {"pub_id": pub_id}
    return query, params


def by_geneset_id(geneset_id: int) -> tuple[Composed, dict]:
    """Create a psycopg query to get a publication by geneset ID.

    :param geneset_id: The geneset ID to search for.

    :return: A query (and params) that can be executed on a cursor.
    """
    query = (
        PUB_QUERY
        + SQL("JOIN geneset ON publication.pub_id = geneset.pub_id")
        + SQL("WHERE gs_id = %(geneset_id)s")
    ).join(" ")

    params = {"geneset_id": geneset_id}
    return query, params


def by_pubmed_id(pubmed_id: int) -> tuple[Composed, dict]:
    """Create a psycopg query to get a publication by PubMed ID.

    :param pubmed_id: The PubMed ID to search for.

    :return: A query (and params) that can be executed on a cursor.
    """
    query = (PUB_QUERY + SQL("WHERE pub_pubmed = %(pmid)s")).join(" ")
    # PubMed IDs are integers, but are stored as strings in the database.
    params = {"pmid": str(pubmed_id)}
    return query, params


def by_pubmed_ids(pubmed_ids: Iterable[int]) -> tuple[Composed, dict]:
    """Create a psycopg query to get publications by a list of PubMed IDs.

    :param pubmed_ids: The PubMed IDs to search for.

    :return: A query (and params) that can be executed on a cursor.
    """
    query = (PUB_QUERY + SQL("WHERE pub_pubmed = ANY(%(pubmed_ids)s)")).join(" ")
    params = {"pubmed_ids": list(pubmed_ids)}
    return query, params


def add(
    authors: str,
    title: str,
    abstract: str,
    journal: str,
    pubmed_id: str,
    volume: str | None = None,
    pages: str | None = None,
    month: str | None = None,
    year: int | None = None,
) -> tuple[Composed, dict]:
    """Create a psycopg query to add a publication to the database.

    :param authors: The authors of the publication.
    :param title: The title of the publication.
    :param abstract: The abstract of the publication.
    :param journal: The journal of the publication.
    :param volume: The volume of the publication.
    :param pages: The pages of the publication.
    :param month: The month of the publication.
    :param year: The year of the publication.
    :param pubmed_id: The PubMed ID of the publication.

    :return: A query (and params) that can be executed on a cursor.
    """
    query = (
        SQL("INSERT INTO publication")
        + SQL("(")
        + PUB_INSERT_COLS
        + SQL(")")
        + SQL("VALUES")
        + SQL("(")
        + PUB_INSERT_VALS
        + SQL(")")
        + SQL("RETURNING pub_id")
    ).join(" ")

    params = {
        "pub_authors": authors,
        "pub_title": title,
        "pub_abstract": abstract,
        "pub_journal": journal,
        "pub_volume": volume,
        "pub_pages": pages,
        "pub_month": month,
        "pub_year": year,
        "pub_pubmed": pubmed_id,
    }

    return query, params


def search(
    existing_filters: SQLList,
    existing_params: ParamDict,
    search_text: str | None = None,
) -> tuple[SQLList, ParamDict]:
    """Add the search filter to the query.

    :param existing_filters: The existing filters.
    :param existing_params: The existing parameters.
    :param search_text: The search text to filter by.
    """
    if search_text is not None:
        search_sql, search_params = utils.search_query(PUB_TSVECTOR, search_text)
        existing_filters.append(search_sql)
        existing_params.update(search_params)
    return existing_filters, existing_params
