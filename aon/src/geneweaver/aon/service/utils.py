"""Utility functions for AON services."""

from typing import Optional

from sqlalchemy.orm import Query


def apply_paging(
    query: Query, start: Optional[int] = None, limit: Optional[int] = None
) -> Query:
    """Apply paging to a query.

    :param query: The query to apply paging to.
    :param start: The start index for the query.
    :param limit: The limit for the query.
    :return: The query with paging applied.
    """
    if start is not None:
        query = query.offset(start)
    if limit is not None:
        query = query.limit(limit)
    return query
