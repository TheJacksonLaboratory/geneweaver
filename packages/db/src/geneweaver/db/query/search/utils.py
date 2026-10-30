"""Functions for generating search queries."""

import re
from enum import Enum

from geneweaver.db.query.utils import (
    ParamDict,
    SQLList,
)
from psycopg.sql import SQL, Composed, Placeholder

#: ``OR`` in capitals, between terms, means either. Lower case stays an ordinary (stop) word, so
#: text such as "alcohol or drug" searches as it always did.
_OR_OPERATOR = re.compile(r"\s+OR\s+")


class SearchConfig(Enum):
    """Search configuration options."""

    SIMPLE = "simple"
    ENGLISH = "english"

    def __str__(self: "SearchConfig") -> str:
        """Render the value as a string."""
        return self.value


class QueryType(Enum):
    """Postgresql Query Type."""

    PLAINTO = "plainto_tsquery"
    PHRASETO = "phraseto_tsquery"
    WEBSEARCH = "websearch_to_tsquery"

    def __str__(self: "SearchConfig") -> str:
        """Render the value as a string."""
        return self.value


SEARCH_QUERIES = {
    QueryType.PLAINTO: SQL("@@ plainto_tsquery({search_config}, %(search)s)"),
    QueryType.PHRASETO: SQL("@@ phraseto_tsquery({search_config}, %(search)s)"),
    QueryType.WEBSEARCH: SQL("@@ websearch_to_tsquery({search_config}, %(search)s)"),
}


def search_query(
    search_column: Composed,
    search_string: str,
    search_config: SearchConfig = SearchConfig.ENGLISH,
    query_type: QueryType = QueryType.WEBSEARCH,
) -> tuple[Composed, dict]:
    """Generate a search query.

    Works generically with any table that has a search column.

    :param search_column: The column to search.
    :param search_string: The string to search for.
    :param search_config: The search configuration to use.
    :param query_type: The query type to use.
    """
    query = SEARCH_QUERIES[query_type].format(search_config=str(search_config))
    return search_column + query, {"search": search_string}


def search(
    existing_filters: SQLList,
    existing_params: ParamDict,
    tsvector_col: Composed,
    search_text: str | None = None,
) -> tuple[SQLList, ParamDict]:
    """Add the search filter to the query.

    :param existing_filters: The existing filters.
    :param existing_params: The existing parameters.
    :param tsvector_col: The tsvector column to search.
    :param search_text: The search text to filter by.
    """
    if search_text is not None:
        alternatives = [part.strip() for part in _OR_OPERATOR.split(search_text) if part.strip()]
        if len(alternatives) > 1:
            search_sql, search_params = _any_of_query(tsvector_col, alternatives)
        else:
            search_sql, search_params = search_query(
                tsvector_col, search_text, query_type=QueryType.PLAINTO
            )
        existing_filters.append(search_sql)
        existing_params.update(search_params)
    return existing_filters, existing_params


def _any_of_query(
    search_column: Composed,
    alternatives: list[str],
    search_config: SearchConfig = SearchConfig.ENGLISH,
) -> tuple[Composed, dict]:
    """Match a row holding every word of at least one of the alternatives.

    Each alternative goes through ``plainto_tsquery``, as a single search does, so its words are
    ANDed and hyphenated terms make no phrase constraint (see ``test_search_uses_plainto``).
    The alternatives are ORed with tsquery's ``||``, so "alcohol AND RNA-seq OR cocaine" is
    (alcohol and RNA-seq) or cocaine. ``AND`` needs no handling: it is a stop word.
    """
    queries = [
        SQL("plainto_tsquery({search_config}, {term})").format(
            search_config=str(search_config), term=Placeholder(f"search_{i}")
        )
        for i in range(len(alternatives))
    ]
    query = SQL("@@ (") + SQL(" || ").join(queries) + SQL(")")
    params = {f"search_{i}": text for i, text in enumerate(alternatives)}
    return search_column + query, params
