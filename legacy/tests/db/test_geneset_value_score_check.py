"""
Regression tests for get_geneset_values_for_score_check (G3-812).

The geneset edit page can change a geneset's score type (GWC-42), but only the
upload paths ran the value-domain check, so a curator could reinterpret existing
values under a new type with no signal that they are nonsensical. update_geneset
now runs score_type_value_warnings against the geneset's stored values; this helper
fetches those values as the (identifier, value) pairs that helper expects.

These pin the fetch: one pair per row, from extsrc.geneset_value, identifier first.
Pure unit tests -- no database.
Run from legacy/:  python -m unittest tests.db.test_geneset_value_score_check
"""
import unittest
from unittest.mock import patch, MagicMock

from tests.db import _shims

_shims.install()
from src.geneweaverdb import get_geneset_values_for_score_check  # noqa: E402


class GenesetValueScoreCheckTests(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('src.geneweaverdb.PooledCursor')
        mock_pc = self.patcher.start()
        self.cursor = MagicMock()
        self.cursor.fetchall.return_value = []
        mock_pc.return_value.__enter__.return_value = self.cursor

    def tearDown(self):
        self.patcher.stop()

    def _sql(self):
        return ' '.join(self.cursor.execute.call_args[0][0].lower().split())

    def _params(self):
        return self.cursor.execute.call_args[0][1]

    def test_returns_identifier_value_pairs(self):
        self.cursor.fetchall.return_value = [('Ces1g', 7.0), ('Actb', 1.5), ('Cer1', 0.01)]
        self.assertEqual(
            get_geneset_values_for_score_check(408075),
            [('Ces1g', 7.0), ('Actb', 1.5), ('Cer1', 0.01)])

    def test_empty_geneset_returns_empty_list(self):
        self.cursor.fetchall.return_value = []
        self.assertEqual(get_geneset_values_for_score_check(1), [])

    def test_queries_geneset_value_for_that_gs_id(self):
        get_geneset_values_for_score_check(408075)
        sql = self._sql()
        self.assertIn('from extsrc.geneset_value', sql)
        self.assertIn('gsv_value', sql)
        self.assertEqual(self._params(), (408075,))

    def test_pairs_feed_the_domain_warning_helper(self):
        # The pairs must be exactly the shape score_type_value_warnings consumes:
        # (ref, value). Two p-value-invalid values -> a warning.
        from src.geneweaverdb import score_type_value_warnings
        self.cursor.fetchall.return_value = [('Ces1g', 7.0), ('Cer1', 0.01)]
        pairs = get_geneset_values_for_score_check(408075)
        warns = score_type_value_warnings(1, pairs)   # 1 = P-Value, domain [0,1]
        self.assertEqual(len(warns), 1)
        self.assertIn('Ces1g=7.0', warns[0])


if __name__ == '__main__':
    unittest.main()
