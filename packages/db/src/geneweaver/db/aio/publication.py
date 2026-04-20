"""Database code for interacting with Publication table."""

from collections.abc import Iterable

from geneweaver.core.schema.publication import PublicationInfo
from geneweaver.db.query import publication as publication_query
from psycopg import AsyncCursor, rows
from psycopg.rows import Row


async def by_pubmed_id(cursor: AsyncCursor, pubmed_id: int) -> rows.Row | None:
    """Get a publication by PubMed ID.

    :param cursor: The database cursor.
    :param pubmed_id: The PubMed ID to search for.

    :return: optional row using `.fetchone()`
    """
    await cursor.execute(*publication_query.by_pubmed_id(pubmed_id))
    return await cursor.fetchone()


async def by_pubmed_ids(cursor: AsyncCursor, pubmed_ids: Iterable[int]) -> list[rows.Row]:
    """Get publications by a list of PubMed IDs.

    :param cursor: The database cursor.
    :param pubmed_ids: The PubMed IDs to search for.

    :return: list of results using `.fetchall()`
    """
    await cursor.execute(*publication_query.by_pubmed_ids(pubmed_ids))
    return await cursor.fetchall()


async def by_id(cursor: AsyncCursor, pub_id: int) -> rows.Row | None:
    """Get a publication by ID.

    :param cursor: The database cursor.
    :param pub_id: The publication ID (geneweaver internal) to search for.

    :return: optional row using `.fetchone()`
    """
    await cursor.execute(*publication_query.by_id(pub_id))
    return await cursor.fetchone()


async def by_geneset_id(cursor: AsyncCursor, geneset_id: int) -> rows.Row | None:
    """Get a publication by geneset ID.

    :param cursor: The database cursor.
    :param geneset_id: The geneset ID to search for.

    :return: optional row using `.fetchone()`
    """
    await cursor.execute(*publication_query.by_geneset_id(geneset_id))
    return await cursor.fetchone()


async def add(cursor: AsyncCursor, publication: PublicationInfo) -> rows.Row | None:
    """Add a publication to the database.

    :param cursor: The database cursor.
    :param publication: The publication to add.

    :return: optional row using `.fetchone()`
    """
    await cursor.execute(*publication_query.add(**publication.model_dump()))
    return await cursor.fetchone()


async def get(
    cursor: AsyncCursor,
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
) -> list[Row]:
    """Get publications by some criteria.

    :param cursor: An async database cursor.
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
    await cursor.execute(
        *publication_query.get(
            pub_id=pub_id,
            authors=authors,
            title=title,
            abstract=abstract,
            journal=journal,
            volume=volume,
            pages=pages,
            month=month,
            year=year,
            pubmed=pubmed,
            search_text=search_text,
            limit=limit,
            offset=offset,
        )
    )

    return await cursor.fetchall()
