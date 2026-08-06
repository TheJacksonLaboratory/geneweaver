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

* GWC-34 (follow-up) -- create_new_geneset_for_user, the plain UI upload path,
  had the same class of defect and was NOT covered by the fix above, which only
  runs on curator gene edits and delayed-upload commits.

  It passes len(gene_data.split('\n')) to production.create_geneset2, which
  stores that number verbatim and only afterwards calls reparse_geneset_file()
  to resolve identifiers into extsrc.geneset_value. So gs_count held a count of
  submitted *lines* -- including the trailing blank line that split('\n') yields
  for text ending in a newline -- while geneset_value held one row per distinct
  identifier that actually resolved. Verified on dev against GS407881: 8
  submitted identifiers, gs_count 9, 4 rows stored.

Pure unit tests: all external deps are mocked so no DB is needed.
Run from legacy/:  python -m unittest tests.test_geneset_count_maintenance
"""
import sys
import unittest
import urllib.parse
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


class CreateNewGenesetForUserTests(unittest.TestCase):
    """The plain UI upload path (application.py /createGeneset -> create_geneset2)."""

    GS_ID = 407881
    ## GS407881 as Tessa uploaded it: 8 identifiers, text ending in a newline.
    IDENTIFIERS = ['TMIGD3', 'OR7E29P', 'Lnc-TLN2-3', 'Hsa-MiR-4461',
                   'SPDYE13P', 'LINC01002', 'RP11-126O22.7', 'RP11-61G19.2']
    ## len(gene_data.split('\n')) -- 8 identifiers plus the trailing blank line.
    SUBMITTED_LINE_COUNT = 9
    ## What reparse_geneset_file() actually stores: only 4 of the 8 resolve.
    STORED_GENE_COUNT = 4

    def _run(self, stored_gene_count):
        """Drive create_new_geneset_for_user with a mocked DB and capture its SQL."""
        self.cursor = MagicMock()
        self.cursor.fetchone.side_effect = [
            (self.GS_ID,),          # create_geneset2 -> gs_id
            (stored_gene_count,),   # count(*) FROM extsrc.geneset_value
        ]
        self.cursor.fetchall.return_value = []
        uploadfiles.db.PooledCursor.return_value.__enter__.return_value = self.cursor
        uploadfiles.db.get_user.return_value.prefs = '{}'

        form = {
            'pub_year': '', 'pub_title': '', 'pub_pages': '', 'pub_authors': '',
            'pub_volume': '', 'pub_abstract': '', 'pub_pubmed': '', 'pub_month': '',
            'pub_journal': '',
            'permissions': 'private',
            'sp_id': '2',
            'gene_identifier': 'gene_7',
            'gs_threshold_type': '3',
            'gs_name': 'test_dropped_genes',
            'gs_abbreviation': 'tdg',
            'gs_description': 'regression fixture',
            'file_text': '\r\n'.join(self.IDENTIFIERS) + '\r\n',
        }
        result = uploadfiles.create_new_geneset_for_user(
            {'formData': urllib.parse.urlencode(form)}, user_id=1)

        self.calls = [
            ((c.args[0] if c.args else ''), (c.args[1] if len(c.args) > 1 else None))
            for c in self.cursor.execute.call_args_list
        ]
        self.statements = [sql for sql, _ in self.calls]
        return result

    def _index_of(self, *needles):
        for i, s in enumerate(self.statements):
            if all(n.lower() in s.lower() for n in needles):
                return i
        return -1

    def _gs_count_update(self):
        for sql, params in self.calls:
            low = sql.lower()
            if 'update' in low and 'gs_count' in low and 'set' in low:
                return sql, params
        self.fail('nothing corrects gs_count after create_geneset2; it keeps the '
                  'submitted line count that was passed in')

    def test_line_count_passed_to_create_geneset2_is_the_inflated_one(self):
        # Pins the premise the rest of the class rests on: the value handed to the
        # stored procedure really is the line count (9), not the gene count (4).
        # If the upstream arithmetic ever changes, these tests should be revisited
        # rather than silently keep passing.
        self._run(self.STORED_GENE_COUNT)
        idx = self._index_of('create_geneset2')
        self.assertNotEqual(idx, -1, 'create_geneset2 was not called')
        self.assertIn(self.SUBMITTED_LINE_COUNT, self.calls[idx][1],
                      'expected the submitted line count to be passed to create_geneset2')

    def test_gs_count_is_corrected_to_the_stored_gene_count(self):
        # The actual regression: after create_geneset2 has run reparse_geneset_file,
        # gs_count must be rewritten from the rows that exist.
        self._run(self.STORED_GENE_COUNT)
        _, params = self._gs_count_update()
        self.assertEqual(
            params, (self.STORED_GENE_COUNT, self.GS_ID),
            'gs_count was not set to the number of genes actually stored')

    def test_submitted_line_count_never_survives_as_gs_count(self):
        # Direction of the bug: the stored count could only ever be too high.
        self._run(self.STORED_GENE_COUNT)
        _, params = self._gs_count_update()
        self.assertNotIn(
            self.SUBMITTED_LINE_COUNT, params,
            'gs_count still carries the submitted line count (%d) rather than the '
            'stored gene count (%d)' % (self.SUBMITTED_LINE_COUNT, self.STORED_GENE_COUNT))

    def test_count_is_read_from_geneset_value_for_this_geneset(self):
        # A count of the wrong table -- or an unscoped one -- would still "correct"
        # gs_count while writing a different number.
        self._run(self.STORED_GENE_COUNT)
        idx = self._index_of('count(*)', 'extsrc.geneset_value')
        self.assertNotEqual(idx, -1, 'gs_count is not derived from extsrc.geneset_value')
        sql, params = self.calls[idx]
        self.assertIn('where', sql.lower(), 'the count is not scoped to one geneset')
        self.assertEqual(params, (self.GS_ID,),
                         'the count is not bound to this gs_id: %r' % (params,))

    def test_correction_runs_after_create_geneset2(self):
        # Ordering is load-bearing: create_geneset2 is what populates
        # geneset_value (via reparse_geneset_file). Counting before it runs would
        # store 0.
        self._run(self.STORED_GENE_COUNT)
        create_at = self._index_of('create_geneset2')
        update_at = self._index_of('update', 'gs_count', 'set')
        self.assertNotEqual(update_at, -1, 'nothing updates gs_count')
        self.assertLess(create_at, update_at,
                        'gs_count is corrected before the rows it counts are inserted')

    def test_gs_count_update_is_parameterised(self):
        self._run(self.STORED_GENE_COUNT)
        sql, _ = self._gs_count_update()
        self.assertNotIn(str(self.GS_ID), sql,
                         'gs_id is interpolated into the SQL instead of bound: %r' % sql)
        self.assertIn('%s', sql, 'no bind placeholder in the gs_count update')

    def test_empty_geneset_is_still_rejected_and_not_counted(self):
        # The zero-gene guard shares the count that the fix reuses -- it must keep
        # deleting the geneset and returning the user-facing error, and must not
        # fall through to writing gs_count=0 on a set it just deleted.
        result = self._run(0)
        self.assertIn('error', result)
        self.assertNotEqual(result['error'], 'None')
        self.assertNotEqual(self._index_of('update', 'gs_status', 'deleted'), -1,
                            'an empty geneset was not marked deleted')
        self.assertEqual(self._index_of('update', 'gs_count', 'set'), -1,
                         'gs_count was written for a geneset that was just deleted')


if __name__ == '__main__':
    unittest.main()
