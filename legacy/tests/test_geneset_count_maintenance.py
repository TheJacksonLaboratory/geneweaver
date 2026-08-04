"""
Regression tests for geneset gs_count maintenance.

* GWC-34 / G3-782 -- insert_into_geneset_value_by_gsid must set
  production.geneset.gs_count from the rows actually stored in
  extsrc.geneset_value, not from a count of production.temp_geneset_value.

  The INSERT it performs groups by ode_gene_id, so two staged source rows that
  resolve to the same gene (an alias/synonym pair, or a symbol listed twice)
  collapse into a single geneset_value row. Counting the *staged* rows therefore
  over-counted: search reads gs_count while the geneset page does its own
  count(*), so the two disagreed -- reproduced on dev as 3 staged rows / 2
  distinct genes giving gs_count=3 against count(*)=2.

Pure unit tests: all external deps are mocked so no DB is needed.
Run from legacy/:  python -m unittest tests.test_geneset_count_maintenance
"""
import sys
import unittest
from unittest.mock import MagicMock

for _mod in ('geneweaverdb', 'annotator', 'psycopg2', 'requests', 'flask',
             'tools', 'tools.toolcommon'):
    sys.modules[_mod] = MagicMock()

import src.uploadfiles as uploadfiles


class InsertIntoGenesetValueByGsidTests(unittest.TestCase):
    GS_ID = 4242

    def setUp(self):
        self.cursor = MagicMock()
        # the `if g is not None` / `int(g[0]) == int(gsid)` guard
        self.cursor.fetchone.return_value = (self.GS_ID,)
        # make_file_content_string_from_temp_geneset iterates fetchall()
        self.cursor.fetchall.return_value = []
        uploadfiles.db.PooledCursor.return_value.__enter__.return_value = self.cursor

        uploadfiles.insert_into_geneset_value_by_gsid(self.GS_ID)
        self.calls = [
            ((c.args[0] if c.args else ''), (c.args[1] if len(c.args) > 1 else None))
            for c in self.cursor.execute.call_args_list
        ]
        self.statements = [sql for sql, _ in self.calls]

    def _find(self, *needles):
        """Statements containing every needle (case-insensitive)."""
        return [s for s in self.statements
                if all(n.lower() in s.lower() for n in needles)]

    def _index_of(self, *needles):
        """Position of the first statement containing every needle, or -1."""
        for i, s in enumerate(self.statements):
            if all(n.lower() in s.lower() for n in needles):
                return i
        return -1

    def _gs_count_update(self):
        """The (sql, params) call that sets gs_count."""
        for sql, params in self.calls:
            low = sql.lower()
            if 'update' in low and 'gs_count' in low and 'set' in low:
                return sql, params
        self.fail('no statement updates gs_count')

    def test_gs_count_is_derived_from_geneset_value(self):
        # The UPDATE that sets gs_count must read the real stored rows.
        updates = self._find('update', 'geneset', 'gs_count')
        self.assertTrue(updates, 'no statement updates gs_count')
        self.assertTrue(
            any('geneset_value' in u.lower() for u in updates),
            'gs_count is not derived from extsrc.geneset_value: %r' % (updates,))

    def test_staging_table_is_never_counted(self):
        # The pre-fix bug: gs_count came from `count(*) FROM temp_geneset_value`,
        # which double-counts identifiers resolving to the same ode_gene_id. That
        # count was interpolated straight into the UPDATE, so checking only the
        # UPDATE text would miss it -- assert no statement counts the staging
        # table at all.
        for stmt in self.statements:
            normalised = ' '.join(stmt.lower().split())
            self.assertFalse(
                'count(*)' in normalised and 'temp_geneset_value' in normalised,
                'staged rows must not be counted for gs_count: %r' % stmt)

    def test_insert_still_collapses_on_ode_gene_id(self):
        # Guards the pairing: the count above is only correct because the INSERT
        # stores one row per distinct gene. If this grouping ever changes, the
        # count derivation has to be revisited too.
        inserts = self._find('insert into extsrc.geneset_value')
        self.assertTrue(inserts, 'no insert into extsrc.geneset_value')
        self.assertIn('group by gs_id,ode_gene_id', inserts[0].lower().replace(', ', ','))

    def test_gs_count_update_runs_after_the_insert(self):
        # Ordering is load-bearing: the count is taken from extsrc.geneset_value,
        # which is emptied and refilled by the INSERT. Running the UPDATE first
        # would store the count of the *previous* contents (or 0 on first save).
        insert_at = self._index_of('insert into extsrc.geneset_value')
        update_at = self._index_of('update', 'gs_count', 'set')
        self.assertNotEqual(insert_at, -1, 'no insert into extsrc.geneset_value')
        self.assertNotEqual(update_at, -1, 'no statement updates gs_count')
        self.assertLess(insert_at, update_at,
                        'gs_count is written before the rows it is meant to count')

    def test_count_subquery_is_scoped_to_this_geneset(self):
        # A subquery without a WHERE would count every row in geneset_value and
        # write that to one geneset -- still "derived from geneset_value", so the
        # shape assertions above would not catch it.
        sql, _ = self._gs_count_update()
        after_geneset_value = sql.lower().split('geneset_value', 1)[1]
        self.assertIn('where', after_geneset_value,
                      'count subquery is not restricted to this gs_id: %r' % sql)
        self.assertGreaterEqual(
            after_geneset_value.count('gs_id'), 2,
            'count subquery does not correlate geneset_value to the geneset row: %r' % sql)

    def test_gs_count_update_is_parameterised(self):
        # gsid arrives unvalidated from /updateGenesetGenes (request.args['gs_id']),
        # so it must be bound, not interpolated into the SQL text.
        sql, params = self._gs_count_update()
        self.assertNotIn(str(self.GS_ID), sql,
                         'gsid is interpolated into the SQL instead of bound: %r' % sql)
        self.assertIn('%s', sql, 'no bind placeholder in the gs_count update')
        self.assertEqual(params, (self.GS_ID,),
                         'gsid is not passed as a query parameter')


if __name__ == '__main__':
    unittest.main()
