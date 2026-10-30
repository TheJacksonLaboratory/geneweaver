"""Unit tests for the gene set search db functions, through the package they import."""

from unittest.mock import MagicMock

from geneweaver.db import search as db_search


def test_count_genesets_runs_one_count_and_returns_it() -> None:
    """Called the way the API calls it, paging and sorting included (they are ignored)."""
    cursor = MagicMock()
    cursor.fetchone.return_value = [9956]

    total = db_search.count_genesets(
        cursor,
        is_readable_by=7,
        search_text="alcohol OR cocaine",
        limit=25,
        offset=0,
        sort_by="size",
        sort_order="desc",
    )

    assert total == 9956
    cursor.execute.assert_called_once()
    sql, params = cursor.execute.call_args.args
    assert "SELECT count(*) FROM geneset" in repr(sql)
    assert (params["search_0"], params["search_1"]) == ("alcohol", "cocaine")
