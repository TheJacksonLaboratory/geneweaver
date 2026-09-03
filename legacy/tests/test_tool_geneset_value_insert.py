"""
Regression test for the tool-created geneset_value INSERT (G3-809).

Raised in review of PR #12: the extracted _store_tool_geneset_values built its
PostgreSQL array literals by string interpolation --

    "VALUES (%s,%s,'%s','{\"%s\"}','{%s}',%s,%s);" % (..., '","'.join(sources), ...)

-- so a stored reference identifier containing a quote or a backslash produced a
malformed array literal, and the line interpolated a query string at all, which the
repo guardrail forbids on any SQL being touched. psycopg2 adapts Python lists to
PostgreSQL arrays itself, so the values belong in the parameter tuple.

These pin that: the INSERT carries no hand-built literals, and a hostile ref_id
survives as data in a bound parameter rather than reaching the SQL text.

Pure unit test -- no database. genesetblueprint imports flask and several app modules
at load, none of which _store_tool_geneset_values needs (it is a plain helper, not a
route), so they are stubbed before import.
Run from legacy/:  python -m unittest tests.test_tool_geneset_value_insert
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

for _name in ('flask', 'batch', 'geneweaverdb', 'pubmedsvc', 'annotator',
              'decorators', 'curation_assignments', 'config', 'notifications'):
    sys.modules.setdefault(_name, MagicMock())

from src import genesetblueprint  # noqa: E402

# A ref_id that breaks a hand-built array literal: a double quote closes the element,
# the backslash escapes, and the semicolon would end the statement.
HOSTILE_REF = 'ABC", "X\\"); DROP TABLE extsrc.geneset_value; --'


class ToolGenesetValueInsertTests(unittest.TestCase):
    def setUp(self):
        self.cursor = MagicMock()
        self.patcher = patch.object(genesetblueprint, 'geneweaverdb')
        gdb = self.patcher.start()
        gdb.PooledCursor.return_value.__enter__.return_value = self.cursor

    def tearDown(self):
        self.patcher.stop()

    def _store(self, ref_id):
        genesetblueprint._store_tool_geneset_values(
            123, [7], [{'ode_gene_id': 7, 'ref_id': ref_id, 'value': 2}])

    def _insert_call(self):
        """The execute() call that inserts into geneset_value."""
        for call in self.cursor.execute.call_args_list:
            sql = call[0][0]
            if isinstance(sql, str) and 'INSERT INTO extsrc.geneset_value' in sql:
                return call
        self.fail('no geneset_value INSERT was issued')

    def test_insert_is_parameterised(self):
        self._store('MGI:12345')
        call = self._insert_call()
        self.assertEqual(len(call[0]), 2,
                         'INSERT was executed without a parameter tuple -- the values '
                         'are being interpolated into the SQL again (G3-809)')
        sql = call[0][0]
        self.assertNotIn("'{", sql, 'hand-built array literal left in the SQL')
        self.assertNotIn('"', sql, 'hand-built quoted array element left in the SQL')
        self.assertEqual(sql.count('%s'), 7)

    def test_hostile_ref_id_stays_in_parameters(self):
        self._store(HOSTILE_REF)
        sql, params = self._insert_call()[0]
        # The identifier must never reach the statement text.
        self.assertNotIn('DROP TABLE', sql)
        # It must arrive verbatim as a list element, for psycopg2 to adapt into a
        # text[] -- unescaped and unquoted, exactly as stored.
        self.assertEqual([HOSTILE_REF], params[3])

    def test_value_list_is_bound_as_a_list(self):
        self._store('MGI:12345')
        _sql, params = self._insert_call()[0]
        self.assertEqual([2], params[4])


if __name__ == '__main__':
    unittest.main()
