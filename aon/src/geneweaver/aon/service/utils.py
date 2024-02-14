from typing import Optional

from sqlalchemy.orm import Query


def apply_paging(
    query: Query, start: Optional[int] = None, limit: Optional[int] = None
) -> Query:
    if start is not None:
        query = query.offset(start)
    if limit is not None:
        query = query.limit(limit)
    return query
