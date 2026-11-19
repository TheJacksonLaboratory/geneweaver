"""Test the geneset.readable_ids function: one query for many gene sets (G3-801)."""

from geneweaver.db.geneset import readable_ids
from psycopg.sql import Composed

from tests.unit.testing_utils import create_execute_raises_error_test


def _rendered(query) -> str:
    def walk(part) -> str:
        if isinstance(part, Composed):
            return "".join(walk(p) for p in part)
        return part.as_string(None)

    return " ".join(walk(query).split())


def test_the_readable_ones_are_returned(cursor):
    """Ids come back as the set of rows the predicate keeps."""
    cursor.fetchall.return_value = [(5,), (7,)]

    assert readable_ids(cursor, 3, [5, 6, 7]) == {5, 7}
    query, params = cursor.execute.call_args.args
    assert params == {"gs_ids": [5, 6, 7], "user_id": 3}
    sql = _rendered(query)
    assert "geneset.gs_id = ANY(%(gs_ids)s)" in sql
    # The shared rule, as search and ABBA apply it, for this user.
    assert "geneset.usr_id = %(user_id)s" in sql
    assert "u.usr_admin > 0 AND u.usr_id = %(user_id)s" in sql


def test_no_gene_sets_needs_no_query(cursor):
    """Nothing to check."""
    assert readable_ids(cursor, 3, []) == set()
    cursor.execute.assert_not_called()


test_readable_ids_execute_raises_error = create_execute_raises_error_test(readable_ids, 1, [1])
