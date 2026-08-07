"""
Regression tests for gene identifier resolution on upload (GWC-36 / G3-768).

get_gene_ids_by_spid_type() builds the ode_ref_id -> ode_gene_id map that the
batch upload path uses to turn the identifiers a user submits into genes. It used
to restrict Gene-Symbol lookups to ode_pref = 't', which resolved the symbol
collision problem (mouse `Ccr4` is the preferred symbol of Ccr4 and *also* a
synonym of Cnot6) but silently DROPPED every gene whose submitted name is only
ever an alias -- 65,019 of 105,975 distinct human symbols on dev, hitting lncRNAs
and renamed genes hardest.

The fix keeps both properties at once, in SQL:

    SELECT DISTINCT ON (lower(ode_ref_id)) lower(ode_ref_id), ode_gene_id
    ...
    ORDER BY lower(ode_ref_id), ode_pref DESC NULLS LAST, ode_gene_id

`ode_pref` moved out of the WHERE clause (so aliases resolve) and into the ORDER
BY (so the preferred row is the one DISTINCT ON keeps, preserving the Ccr4/Cnot6
disambiguation). Those two facts are what these tests pin: dropping either one
reintroduces a silent data-loss bug that no user-visible error reports.

Related: GWC-34 / G3-782 made gs_count report the genes actually stored, so genes
lost here now visibly shrink the displayed count instead of hiding behind an
inflated one.

Pure unit tests -- no database. Run from legacy/:
    python -m unittest tests.db.test_gene_id_mapping
"""
import unittest
from unittest.mock import patch, MagicMock

from tests.db import _shims

_shims.install()
from src.geneweaverdb import get_gene_ids_by_spid_type  # noqa: E402

SYMBOL_GDB_ID = 7      # Gene Symbol -- the type that used to be pref-filtered
ENSEMBL_GDB_ID = 2     # a type that never was
SP_ID = 2              # human


class GeneIdMappingTests(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('src.geneweaverdb.PooledCursor')
        mock_pc = self.patcher.start()
        self.cursor = MagicMock()
        self.cursor.fetchall.return_value = []
        mock_pc.return_value.__enter__.return_value = self.cursor

    def tearDown(self):
        self.patcher.stop()

    def _sql(self, normalise=True):
        sql = self.cursor.execute.call_args[0][0]
        return ' '.join(sql.lower().split()) if normalise else sql

    def _params(self):
        args = self.cursor.execute.call_args[0]
        return args[1] if len(args) > 1 else None

    # --- behaviour ----------------------------------------------------------

    def test_returns_ref_id_to_gene_id_mapping(self):
        self.cursor.fetchall.return_value = [('tmigd3', 105219), ('spdye13p', 94285)]
        self.assertEqual(
            get_gene_ids_by_spid_type(SP_ID, SYMBOL_GDB_ID),
            {'tmigd3': 105219, 'spdye13p': 94285})

    def test_empty_result_returns_empty_dict(self):
        self.cursor.fetchall.return_value = []
        self.assertEqual(get_gene_ids_by_spid_type(SP_ID, SYMBOL_GDB_ID), {})

    def test_alias_only_symbol_is_resolvable(self):
        # SPDYE13P is a non-preferred alias of SPDYE13. Under the pre-fix query it
        # never reached the caller at all and the gene was dropped from the upload.
        self.cursor.fetchall.return_value = [('spdye13p', 94285)]
        self.assertEqual(
            get_gene_ids_by_spid_type(SP_ID, SYMBOL_GDB_ID).get('spdye13p'), 94285)

    # --- the regression -----------------------------------------------------

    def test_lookup_is_not_restricted_to_preferred_symbols(self):
        # THE bug: `ode_pref = 't'` in the WHERE clause excluded alias-only genes.
        # ode_pref may appear only after ORDER BY (for collision precedence), so
        # assert on the part of the statement that selects rows.
        get_gene_ids_by_spid_type(SP_ID, SYMBOL_GDB_ID)
        sql = self._sql()
        self.assertIn('order by', sql, 'query lost its ORDER BY')
        selecting = sql.split('order by', 1)[0]
        self.assertNotIn(
            'ode_pref', selecting,
            'ode_pref is filtering rows again -- alias-only symbols will be '
            'silently dropped on upload (GWC-36): %r' % sql)

    def test_preferred_row_wins_on_collision(self):
        # The other half: without ode_pref DESC leading the tie-break, a symbol
        # that is preferred for one gene and an alias of another could resolve to
        # the wrong gene (the Ccr4/Cnot6 case the pref filter originally existed
        # to solve).
        get_gene_ids_by_spid_type(SP_ID, SYMBOL_GDB_ID)
        sql = self._sql()
        ordering = sql.split('order by', 1)[1]
        self.assertIn('ode_pref desc', ordering,
                      'preferred rows must sort first so DISTINCT ON keeps them: %r' % sql)

    def test_one_row_per_symbol_is_enforced_in_sql(self):
        # The de-duplication that makes the ordering meaningful. If DISTINCT ON is
        # dropped, every alias row crosses the wire and the dict is built by
        # last-write-wins in Python -- i.e. the *opposite* precedence.
        get_gene_ids_by_spid_type(SP_ID, SYMBOL_GDB_ID)
        sql = self._sql()
        self.assertIn('distinct on (lower(ode_ref_id))', sql,
                      'lost the one-row-per-symbol guarantee: %r' % sql)

    def test_collision_precedence_survives_python_dict_building(self):
        # End-to-end on the contract above: the DB hands back the preferred row
        # for a colliding symbol, and the function must not undo that.
        self.cursor.fetchall.return_value = [('ccr4', 111), ('cnot6', 222)]
        self.assertEqual(
            get_gene_ids_by_spid_type(SP_ID, SYMBOL_GDB_ID)['ccr4'], 111)

    def test_symbols_are_matched_case_insensitively(self):
        # Users paste mixed case; the map is keyed on lower(ode_ref_id) and batch
        # lowercases before lookup. Losing this drops correctly-spelled genes.
        get_gene_ids_by_spid_type(SP_ID, SYMBOL_GDB_ID)
        self.assertIn('lower(ode_ref_id)', self._sql())

    # --- shape of the query -------------------------------------------------

    def test_same_query_regardless_of_identifier_type(self):
        # The pre-fix code asked get_gene_id_types() whether this gdb_id was the
        # symbol type and branched to a second, pref-filtered query. One query for
        # every type is what removes that failure mode.
        get_gene_ids_by_spid_type(SP_ID, SYMBOL_GDB_ID)
        symbol_sql = self._sql()
        self.cursor.reset_mock()
        get_gene_ids_by_spid_type(SP_ID, ENSEMBL_GDB_ID)
        self.assertEqual(symbol_sql, self._sql(),
                         'identifier type is being special-cased again')

    def test_issues_a_single_query(self):
        get_gene_ids_by_spid_type(SP_ID, SYMBOL_GDB_ID)
        self.assertEqual(self.cursor.execute.call_count, 1)

    def test_query_is_parameterised(self):
        # sp_id / gdb_id originate in upload form data.
        get_gene_ids_by_spid_type(SP_ID, SYMBOL_GDB_ID)
        self.assertEqual(self._params(), (SP_ID, SYMBOL_GDB_ID))
        self.assertNotIn(str(SYMBOL_GDB_ID), self._sql(normalise=False).replace('%s', ''),
                         'identifier type is interpolated into the SQL text')


if __name__ == '__main__':
    unittest.main()
