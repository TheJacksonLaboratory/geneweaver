"""Tests for the search() utility function."""

import pytest
from geneweaver.db.query.search.utils import search
from psycopg.sql import SQL

TSVECTOR_COL = SQL("_combined_tsvector")


def test_search_uses_plainto_tsquery_by_default():
    """search() must use plainto_tsquery, not websearch_to_tsquery.

    websearch_to_tsquery generates phrase constraints (<->) for hyphenated
    terms, causing silent search failures for disease names like
    'Shwachman-Diamond syndrome'. plainto_tsquery treats each token
    independently and returns correct results.
    """
    filters, _params = search([], {}, TSVECTOR_COL, search_text="Shwachman-Diamond syndrome")
    assert len(filters) == 1
    sql_str = str(filters[0])
    assert "plainto_tsquery" in sql_str
    assert "websearch_to_tsquery" not in sql_str
    assert "phraseto_tsquery" not in sql_str


def test_search_no_text_returns_unchanged():
    """search() with no search_text leaves filters and params unchanged."""
    existing_filters = [SQL("gs_status = 0")]
    existing_params = {"status": 0}
    filters, params = search(existing_filters, existing_params, TSVECTOR_COL, search_text=None)
    assert filters == existing_filters
    assert params == existing_params


def test_search_appends_filter():
    """search() appends exactly one filter when search_text is provided."""
    filters, params = search([], {}, TSVECTOR_COL, search_text="alcohol")
    assert len(filters) == 1
    assert "search" in params
    assert params["search"] == "alcohol"


def test_search_preserves_existing_filters():
    """search() does not remove pre-existing filters."""
    pre = [SQL("sp_id = %(sp)s")]
    pre_params = {"sp": 1}
    filters, params = search(pre, pre_params, TSVECTOR_COL, search_text="depression")
    assert len(filters) == 2
    assert params["sp"] == 1
    assert params["search"] == "depression"


@pytest.mark.parametrize(
    "term",
    [
        "Shwachman-Diamond syndrome 1",
        "Camurati-Engelmann disease",
        "Alpha-mannosidosis",
        "Galloway-Mowat syndrome 2, X-linked",
        "PURA-related severe neonatal hypotonia-seizures-encephalopathy syndrome",
        "17q11 microdeletion syndrome",
        "toxic shock syndrome",
    ],
)
def test_search_hyphenated_terms_use_plainto(term):
    """Hyphenated and complex disease names must not produce phrase constraints."""
    filters, params = search([], {}, TSVECTOR_COL, search_text=term)
    sql_str = str(filters[0])
    assert "plainto_tsquery" in sql_str
    assert "websearch_to_tsquery" not in sql_str
    assert params["search"] == term


def test_search_or_is_the_union_of_each_alternatives_words():
    """ "A AND B OR C" is (A and B) or C: each side is its own plainto_tsquery."""
    filters, params = search([], {}, TSVECTOR_COL, search_text="alcohol AND RNA-seq OR cocaine")
    assert len(filters) == 1
    sql_str = str(filters[0])
    assert sql_str.count("plainto_tsquery") == 2
    assert " || " in sql_str
    assert "websearch_to_tsquery" not in sql_str
    assert params == {"search_0": "alcohol AND RNA-seq", "search_1": "cocaine"}


def test_search_lower_case_or_is_not_an_operator():
    """Only OR in capitals is an operator, so "alcohol or drug" searches as it always did."""
    filters, params = search([], {}, TSVECTOR_COL, search_text="alcohol or drug")
    assert str(filters[0]).count("plainto_tsquery") == 1
    assert params == {"search": "alcohol or drug"}


@pytest.mark.parametrize("term", ["alcohol OR", "OR alcohol", "alcohol OR OR  "])
def test_search_a_dangling_or_searches_what_is_left(term):
    """An OR with nothing beside it neither errors nor matches everything."""
    filters, params = search([], {}, TSVECTOR_COL, search_text=term)
    assert len(filters) == 1
    assert "alcohol" in " ".join(str(v) for v in params.values())


def test_search_comma_separated_terms_are_one_and_query():
    """Commas separate terms for a person; plainto_tsquery already ANDs them."""
    filters, params = search([], {}, TSVECTOR_COL, search_text="alcohol, RNA-seq")
    assert str(filters[0]).count("plainto_tsquery") == 1
    assert params == {"search": "alcohol, RNA-seq"}
