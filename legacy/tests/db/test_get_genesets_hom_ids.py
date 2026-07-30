"""
Regression tests for the "Find Similar Genesets" homology-id queries in
geneweaverdb (GWC-35 / G3-780).

The Jaccard similarity on the geneset view must count only in-threshold genes on
BOTH sides:
* the viewed geneset   -> get_geneset_hom_ids   (always filtered)
* each candidate       -> get_genesets_hom_ids  (the fix: previously read the
                          unthresholded extsrc.geneset2hom materialized view)

These are DB functions, but they can be unit-tested with no database: geneweaverdb
builds a connection pool at import (minconn=5), so we install a fake psycopg2 whose
pool __init__ is a no-op, mock the external imports, and patch PooledCursor to feed
canned rows. We assert the return shape AND that each query filters gsv_in_threshold
(and that the candidate query no longer uses the unthresholded geneset2hom view).

Run from legacy/:  python -m unittest tests.db.test_get_genesets_hom_ids
"""
import sys
import types
import unittest
from unittest.mock import patch, MagicMock


def _install_import_shims():
    """Make `import src.geneweaverdb` succeed with no DB / no psycopg2 installed."""
    # Fake psycopg2 tree. The pool base class must be a REAL class (it is
    # subclassed) with a no-op __init__ so the module-level pool() doesn't connect.
    psycopg2 = types.ModuleType('psycopg2')
    psycopg2.Error = type('Error', (Exception,), {})
    psycopg2.sql = MagicMock()
    extras = types.ModuleType('psycopg2.extras')
    extras.execute_values = MagicMock()
    pool = types.ModuleType('psycopg2.pool')

    class _NoConnectPool:
        def __init__(self, *a, **k):
            pass

        def getconn(self, *a, **k):
            raise AssertionError('PooledCursor must be mocked in these tests')

        def putconn(self, *a, **k):
            pass

    pool.ThreadedConnectionPool = _NoConnectPool
    psycopg2.extras = extras
    psycopg2.pool = pool
    sys.modules['psycopg2'] = psycopg2
    sys.modules['psycopg2.extras'] = extras
    sys.modules['psycopg2.pool'] = pool

    # Everything else geneweaverdb imports at module load.
    for name in ('config', 'notifications', 'pubmedsvc', 'annotator',
                 'curation_assignments', 'flask', 'tools', 'tools.toolcommon'):
        sys.modules.setdefault(name, MagicMock())


_install_import_shims()
from src.geneweaverdb import get_genesets_hom_ids, get_geneset_hom_ids  # noqa: E402


class FindSimilarThresholdQueryTests(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('src.geneweaverdb.PooledCursor')
        mock_pc = self.patcher.start()
        self.cursor = MagicMock()
        mock_pc.return_value.__enter__.return_value = self.cursor

    def tearDown(self):
        self.patcher.stop()

    def _executed_sql(self):
        return self.cursor.execute.call_args[0][0]

    # --- candidate side: the GWC-35 fix -------------------------------------
    def test_candidates_return_mapping(self):
        self.cursor.rowcount = 2
        self.cursor.fetchall.return_value = [(1, [10, 20]), (2, [30])]
        self.assertEqual(get_genesets_hom_ids([1, 2]), {1: [10, 20], 2: [30]})

    def test_candidates_query_filters_in_threshold(self):
        self.cursor.rowcount = 1
        self.cursor.fetchall.return_value = [(1, [10])]
        get_genesets_hom_ids([1])
        sql = self._executed_sql()
        self.assertIn('gsv_in_threshold', sql,
                      'candidate similarity query must threshold candidate genes (GWC-35)')

    def test_candidates_no_longer_use_unthresholded_matview(self):
        self.cursor.rowcount = 1
        self.cursor.fetchall.return_value = [(1, [10])]
        get_genesets_hom_ids([1])
        self.assertNotIn('geneset2hom', self._executed_sql(),
                         'must not read the unthresholded geneset2hom materialized view')

    def test_candidates_empty_returns_empty_dict(self):
        self.cursor.rowcount = 0
        self.cursor.fetchall.return_value = []
        self.assertEqual(get_genesets_hom_ids([9999]), {})

    # --- viewed side: unchanged, but lock in the invariant ------------------
    def test_viewed_query_filters_in_threshold(self):
        self.cursor.rowcount = 3
        self.cursor.fetchall.return_value = [(10,), (20,), (30,)]
        self.assertEqual(get_geneset_hom_ids(1), [10, 20, 30])
        self.assertIn('gsv_in_threshold', self._executed_sql())

    def test_viewed_empty_returns_zero(self):
        self.cursor.rowcount = 0
        self.assertEqual(get_geneset_hom_ids(1), 0)


if __name__ == '__main__':
    unittest.main()
