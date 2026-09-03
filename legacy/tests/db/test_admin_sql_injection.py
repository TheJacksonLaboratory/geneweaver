"""
Regression tests for the admin data-table SQL injection sinks (G3-816).

Found during the G3-806 SQA sign-off. These endpoints built SQL by
%-interpolating request parameters and ran it with no bound parameters, so
`search[value]`, `table` and `columns[N][name]` all reached the query text
unescaped. psycopg2's execute() hands the string to libpq PQexec, so statements
stacked after a `;` executed too -- write and DDL, not just read.

Two of the routes (/getServersideGenesetsdb, /getServersideResultsdb) had no
authentication at all and took the `user_id` to filter on from the request, so the
injection was reachable unauthenticated and any user's rows could be listed by
guessing an id. Those functions now require the caller to pass the session user.

What is asserted here, and why in this shape: the genesets/results queries are
assembled as plain strings with %s placeholders, so the tests can prove the search
value never reaches the query text and arrives as a bound parameter instead. The
admin viewer's query is built with psycopg2.sql composition, which under the test
shim (no psycopg2 in CI -- see tests/db/_shims) is a MagicMock, so for that one the
assertions are on the rejection paths and on the fact that values are bound at all.

Pure unit tests -- no database.
Run from legacy/:  python -m unittest tests.db.test_admin_sql_injection
"""
import unittest
from unittest.mock import patch, MagicMock

from tests.db import _shims

_shims.install()
from src import geneweaverdb  # noqa: E402

## A value that breaks out of a hand-built `LIKE '%...%'` literal and stacks a
## second statement -- the payload shape recorded on G3-816.
BREAKOUT = "'); DROP TABLE production.geneset; --"


class FakeArgs(dict):
    """Minimal stand-in for a Flask request MultiDict."""

    def get(self, key, default=None, type=None):
        if key not in self:
            return default
        value = dict.get(self, key)
        if type is not None:
            try:
                return type(value)
            except (TypeError, ValueError):
                return default
        return value


class AdminTableAllowlistTests(unittest.TestCase):
    """Identifiers cannot be bound, so the table name is allowlisted instead."""

    def test_offered_tables_resolve(self):
        for table in ('production.usr', 'production.geneset', 'extsrc.gene',
                      'odestatic.news_feed'):
            self.assertIsNotNone(geneweaverdb._admin_table_ident(table), table)

    def test_table_outside_the_admin_ui_is_rejected(self):
        # A real table, but not one the admin viewer offers.
        self.assertIsNone(geneweaverdb._admin_table_ident('production.result'))

    def test_injection_attempts_are_rejected(self):
        for table in ("production.usr; DROP TABLE production.geneset; --",
                      "production.usr'--",
                      "(SELECT apikey FROM production.usr)",
                      "production.usr WHERE 1=1"):
            self.assertIsNone(geneweaverdb._admin_table_ident(table), table)

    def test_empty_and_none_are_rejected(self):
        self.assertIsNone(geneweaverdb._admin_table_ident(''))
        self.assertIsNone(geneweaverdb._admin_table_ident(None))


class GetServerSideTests(unittest.TestCase):
    """/admin/serversidedb -- the primary sink."""

    def setUp(self):
        self.patcher = patch('src.geneweaverdb.PooledCursor')
        mock_pc = self.patcher.start()
        self.cursor = MagicMock()
        self.cursor.fetchall.return_value = []
        self.cursor.fetchone.return_value = [0]
        mock_pc.return_value.__enter__.return_value = self.cursor
        self.cols = patch('src.geneweaverdb._admin_table_columns',
                          return_value={'usr_id', 'usr_email', 'apikey'})
        self.cols.start()

    def tearDown(self):
        self.patcher.stop()
        self.cols.stop()

    def test_arbitrary_from_is_refused_without_touching_the_database(self):
        result = geneweaverdb.get_server_side(FakeArgs({
            'table': 'production.result', 'columns[0][name]': 'res_id'}))
        self.assertIn('error', result)
        self.assertEqual([], result['aaData'])
        self.cursor.execute.assert_not_called()

    def test_column_not_belonging_to_the_table_is_refused(self):
        result = geneweaverdb.get_server_side(FakeArgs({
            'table': 'production.usr',
            'columns[0][name]': '(SELECT apikey FROM production.usr LIMIT 1)'}))
        self.assertIn('error', result)
        self.cursor.execute.assert_not_called()

    def test_no_columns_requested_is_refused(self):
        result = geneweaverdb.get_server_side(FakeArgs({'table': 'production.usr'}))
        self.assertIn('error', result)
        self.cursor.execute.assert_not_called()

    def test_search_value_is_bound_not_interpolated(self):
        geneweaverdb.get_server_side(FakeArgs({
            'table': 'production.usr',
            'columns[0][name]': 'usr_id',
            'columns[1][name]': 'usr_email',
            'search[value]': BREAKOUT,
        }))
        first = self.cursor.execute.call_args_list[0][0]
        self.assertEqual(2, len(first),
                         'query executed with no parameter tuple -- values are being '
                         'interpolated into the SQL again (G3-816)')
        # One bound pattern per searched column, each carrying the payload as data.
        self.assertEqual(['%' + BREAKOUT + '%'] * 2, first[1])


class GenesetsAndResultsBindingTests(unittest.TestCase):
    """The two formerly unauthenticated endpoints."""

    def setUp(self):
        self.patcher = patch('src.geneweaverdb.PooledCursor')
        mock_pc = self.patcher.start()
        self.cursor = MagicMock()
        self.cursor.fetchall.return_value = []
        self.cursor.fetchone.return_value = [0]
        mock_pc.return_value.__enter__.return_value = self.cursor

    def tearDown(self):
        self.patcher.stop()

    def _first_call(self):
        return self.cursor.execute.call_args_list[0][0]

    def _run(self, fn, **extra):
        args = FakeArgs({'search[value]': BREAKOUT, 'order[0][column]': 1,
                         'order[0][dir]': 'asc'})
        args.update(extra)
        return fn(args, 42)

    def test_genesets_search_value_never_reaches_the_query_text(self):
        self._run(geneweaverdb.get_server_side_genesets)
        query, params = self._first_call()
        self.assertNotIn('DROP TABLE', query)
        self.assertNotIn(BREAKOUT, query)
        self.assertIn('%s', query)
        self.assertIn('%' + BREAKOUT + '%', params)

    def test_results_search_value_never_reaches_the_query_text(self):
        self._run(geneweaverdb.get_server_side_results)
        query, params = self._first_call()
        self.assertNotIn('DROP TABLE', query)
        self.assertNotIn(BREAKOUT, query)
        self.assertIn('%' + BREAKOUT + '%', params)

    def test_user_id_comes_from_the_caller_not_the_request(self):
        # A request-supplied user_id must be ignored: it used to let anyone list
        # another user's rows on an unauthenticated route.
        self._run(geneweaverdb.get_server_side_genesets, **{'user_id': 999})
        _query, params = self._first_call()
        self.assertEqual(42, params[0])
        self.assertNotIn(999, params)

    def test_user_id_is_bound(self):
        self._run(geneweaverdb.get_server_side_results)
        query, params = self._first_call()
        self.assertIn('usr_id=%s', query)
        self.assertEqual(42, params[0])

    def test_out_of_range_sort_index_does_not_raise(self):
        # select_columns is a fixed list; an out-of-range index used to IndexError.
        for idx in (99, -5):
            self.cursor.reset_mock()
            self._run(geneweaverdb.get_server_side_genesets,
                      **{'order[0][column]': idx})
            query, _params = self._first_call()
            self.assertNotIn('ORDER BY', query)


class AdminDeleteTests(unittest.TestCase):
    """The DELETE sink -- this one destroys data."""

    def setUp(self):
        self.patcher = patch('src.geneweaverdb.PooledCursor')
        mock_pc = self.patcher.start()
        self.cursor = MagicMock()
        mock_pc.return_value.__enter__.return_value = self.cursor
        self.cols = patch('src.geneweaverdb._admin_table_columns',
                          return_value={'usr_id', 'usr_email'})
        self.cols.start()

    def tearDown(self):
        self.patcher.stop()
        self.cols.stop()

    def test_unknown_table_is_refused(self):
        result = geneweaverdb.admin_delete(FakeArgs({'table': 'production.result'}),
                                           ["res_id='1'"])
        self.assertEqual("Error: Unknown table", result)
        self.cursor.execute.assert_not_called()

    def test_unknown_key_column_is_refused(self):
        result = geneweaverdb.admin_delete(FakeArgs({'table': 'production.usr'}),
                                           ["apikey='x'"])
        self.assertEqual("Error: Unknown primary key column", result)
        self.cursor.execute.assert_not_called()

    def test_key_value_is_bound_so_it_cannot_widen_the_where(self):
        # "' OR '1'='1" used to produce WHERE usr_id='' OR '1'='1' -- whole table.
        widen = "' OR '1'='1"
        geneweaverdb.admin_delete(FakeArgs({'table': 'production.usr'}),
                                  ["usr_id='%s'" % widen])
        args = self.cursor.execute.call_args[0]
        self.assertEqual(2, len(args), 'DELETE executed with no parameter tuple')
        self.assertEqual([widen], args[1])

    def test_no_keys_is_refused(self):
        result = geneweaverdb.admin_delete(FakeArgs({'table': 'production.usr'}), [])
        self.assertEqual("Error: No primary key constraints set.", result)
        self.cursor.execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
