"""
Unit tests for geneweaverdb.get_genesets_with_threshold_counts.

The function returns the number of in-threshold genes for each of the given
genesets. It backs the "134 (12)" display on the Analyze Genesets and geneset
overlap pages, and is what G3-785 will reuse to put the same figure in search
results.

    get_genesets_with_threshold_counts([1, 2]) -> {1: 10, 2: 20}

NOTE ON THIS FILE'S HISTORY. It previously could not run at all, and was invisible
because it is not in the CI gate (.github/workflows/_legacy-tests.yml). It
imported `get_geneset_ids_with_threshold_counts`, which does not exist -- the
function is `get_genesets_with_threshold_counts` -- and then called a third name
it never imported. Its assertions were also written against an imagined API,
expecting a list of dicts like [{"geneset_id": 1, "threshold_count": 10}] where
the function returns a plain {gs_id: count} dict, so all four tests would have
failed even once the import was corrected. Rewritten here against the real
signature and added to the CI gate so it cannot rot unnoticed again.

Pure unit tests -- no database. Run from legacy/:
    python -m unittest tests.db.test_get_genesets_w_threshold_counts
"""
import unittest
from unittest.mock import patch, MagicMock

from tests.db import _shims

_shims.install()
from src.geneweaverdb import get_genesets_with_threshold_counts  # noqa: E402


class GetGenesetsWithThresholdCountsTests(unittest.TestCase):
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
        args = self.cursor.execute.call_args[0]
        return args[1] if len(args) > 1 else None

    # --- return shape -------------------------------------------------------

    def test_returns_gs_id_to_count_mapping(self):
        self.cursor.fetchall.return_value = [(1, 10), (2, 20), (3, 5)]
        self.assertEqual(get_genesets_with_threshold_counts([1, 2, 3]),
                         {1: 10, 2: 20, 3: 5})

    def test_no_rows_returns_empty_dict(self):
        self.cursor.fetchall.return_value = []
        self.assertEqual(get_genesets_with_threshold_counts([9999]), {})

    def test_empty_id_list_returns_empty_dict(self):
        self.cursor.fetchall.return_value = []
        self.assertEqual(get_genesets_with_threshold_counts([]), {})

    def test_genesets_with_no_in_threshold_genes_are_absent_not_zero(self):
        # Load-bearing for callers. The query is a LEFT JOIN, but the WHERE
        # clause tests gv.gsv_in_threshold, which discards the NULL-extended rows
        # and makes it behave as an inner join -- so a geneset with no
        # in-threshold genes produces no row and is simply missing from the dict
        # rather than mapping to 0. viewGenesetSummaryPartial.html subscripts this
        # dict directly, so callers must default the missing keys (G3-785).
        self.cursor.fetchall.return_value = [(1, 10)]
        result = get_genesets_with_threshold_counts([1, 2])
        self.assertEqual(result, {1: 10})
        self.assertNotIn(2, result)
        self.assertEqual(result.get(2, 0), 0, 'callers should default to 0')

    # --- the query -----------------------------------------------------------

    def test_counts_only_in_threshold_values(self):
        get_genesets_with_threshold_counts([1])
        self.assertIn('gsv_in_threshold', self._sql(),
                      'must count only in-threshold genes, not every gene')

    def test_scoped_to_the_requested_genesets(self):
        get_genesets_with_threshold_counts([1, 2])
        sql = self._sql()
        self.assertIn('where', sql)
        self.assertIn('gs.gs_id =', sql,
                      'query is not restricted to the requested genesets: %r' % sql)

    def test_query_is_parameterised(self):
        # geneset_ids reach this from request data on the project/overlap pages.
        get_genesets_with_threshold_counts([1, 2, 3])
        self.assertEqual(self._params(), ([1, 2, 3],))
        self.assertNotIn('9999', self._sql())

    def test_issues_a_single_query(self):
        get_genesets_with_threshold_counts([1, 2, 3])
        self.assertEqual(self.cursor.execute.call_count, 1,
                         'must not query per geneset')


if __name__ == '__main__':
    unittest.main()
