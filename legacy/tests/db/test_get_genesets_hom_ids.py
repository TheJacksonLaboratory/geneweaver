"""
Regression tests for the "Find Similar Genesets" membership queries in
geneweaverdb (GWC-35 / G3-780 / G3-805).

The Jaccard similarity on the geneset view must define membership identically on
both sides, or the score is asymmetric:
* the viewed geneset   -> get_geneset_similarity_keys
* each candidate       -> get_genesets_similarity_keys

Two bugs are pinned here, both of which inflated the similarity:
* G3-780: the candidate side read the unthresholded extsrc.geneset2hom
  materialized view, so candidates contributed out-of-threshold genes.
* G3-805: both sides INNER JOINed extsrc.homology, so an in-threshold gene with
  no homology record vanished from the set -- shrinking the union but never the
  intersection.

Separately, candidate *discovery* (get_geneset_hom_ids -> get_genesets_by_hom_id)
must keep returning real integer hom_ids, because it looks up extsrc.hom2geneset.
That is asserted too, so the scoring fix doesn't get copy-pasted onto it.

These are DB functions, but they can be unit-tested with no database: geneweaverdb
builds a connection pool at import (minconn=5), so we install a fake psycopg2 whose
pool __init__ is a no-op, mock the external imports, and patch PooledCursor to feed
canned rows.

Run from legacy/:  python -m unittest tests.db.test_get_genesets_hom_ids
"""
import re
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
from src.geneweaverdb import (  # noqa: E402
    get_geneset_hom_ids,
    get_geneset_similarity_keys,
    get_genesets_similarity_keys,
)


def _squash(sql):
    """Collapse whitespace so multi-line SQL can be matched as one string."""
    return re.sub(r'\s+', ' ', sql).strip()


class FindSimilarMembershipQueryTests(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('src.geneweaverdb.PooledCursor')
        mock_pc = self.patcher.start()
        self.cursor = MagicMock()
        mock_pc.return_value.__enter__.return_value = self.cursor

    def tearDown(self):
        self.patcher.stop()

    def _executed_sql(self):
        return _squash(self.cursor.execute.call_args[0][0])

    def _run_candidates(self, rows=((1, ['h10']),)):
        self.cursor.rowcount = len(rows)
        self.cursor.fetchall.return_value = list(rows)
        return get_genesets_similarity_keys([1])

    def _run_viewed(self, rows=(('h10',),)):
        self.cursor.rowcount = len(rows)
        self.cursor.fetchall.return_value = list(rows)
        return get_geneset_similarity_keys(1)

    # --- candidate side ------------------------------------------------------
    def test_candidates_return_mapping(self):
        self.cursor.rowcount = 2
        self.cursor.fetchall.return_value = [(1, ['h10', 'h20']), (2, ['g30'])]
        self.assertEqual(get_genesets_similarity_keys([1, 2]),
                         {1: ['h10', 'h20'], 2: ['g30']})

    def test_candidates_query_filters_in_threshold(self):
        self._run_candidates()
        self.assertIn('gsv_in_threshold', self._executed_sql(),
                      'candidate query must threshold candidate genes (G3-780)')

    def test_candidates_no_longer_use_unthresholded_matview(self):
        self._run_candidates()
        self.assertNotIn('geneset2hom', self._executed_sql(),
                         'must not read the unthresholded geneset2hom matview (G3-780)')

    def test_candidates_left_join_homology(self):
        self._run_candidates()
        self.assertIn('LEFT JOIN extsrc.homology', self._executed_sql(),
                      'genes with no homolog must not be dropped from the set (G3-805)')

    def test_candidates_empty_returns_empty_dict(self):
        self.cursor.rowcount = 0
        self.cursor.fetchall.return_value = []
        self.assertEqual(get_genesets_similarity_keys([9999]), {})

    # --- viewed side ---------------------------------------------------------
    def test_viewed_returns_keys(self):
        self.assertEqual(self._run_viewed((('h10',), ('g20',))), ['h10', 'g20'])

    def test_viewed_query_filters_in_threshold(self):
        self._run_viewed()
        self.assertIn('gsv_in_threshold', self._executed_sql())

    def test_viewed_left_join_homology(self):
        self._run_viewed()
        self.assertIn('LEFT JOIN extsrc.homology', self._executed_sql(),
                      'genes with no homolog must not be dropped from the set (G3-805)')

    def test_viewed_empty_returns_zero(self):
        self.cursor.rowcount = 0
        self.assertEqual(get_geneset_similarity_keys(1), 0)

    # --- both sides must agree on what a member IS ---------------------------
    def test_both_sides_use_the_same_membership_key(self):
        """If these drift apart the Jaccard becomes asymmetric again."""
        self._run_viewed()
        viewed_sql = self._executed_sql()
        self.cursor.reset_mock()
        self._run_candidates()
        candidate_sql = self._executed_sql()

        key = _squash("""CASE WHEN h.hom_id IS NULL
                              THEN 'g' || gsv.ode_gene_id
                              ELSE 'h' || h.hom_id END""")
        for name, sql in (('viewed', viewed_sql), ('candidate', candidate_sql)):
            self.assertIn(key, sql,
                          '%s side must key membership by hom_id, falling back to the '
                          'gene itself when it has no homolog' % name)

    # --- discovery path must NOT be changed ----------------------------------
    def test_discovery_still_returns_integer_hom_ids(self):
        """get_geneset_hom_ids feeds get_genesets_by_hom_id -> extsrc.hom2geneset,
        which can only be looked up by real hom_id. It must stay an INNER JOIN
        returning integers -- the similarity-key treatment does not belong here."""
        self.cursor.rowcount = 3
        self.cursor.fetchall.return_value = [(10,), (20,), (30,)]
        self.assertEqual(get_geneset_hom_ids(1), [10, 20, 30])
        sql = self._executed_sql()
        self.assertIn('gsv_in_threshold', sql)
        self.assertNotIn('LEFT JOIN', sql,
                         'discovery must keep the INNER JOIN; hom2geneset needs real hom_ids')

    def test_discovery_empty_returns_zero(self):
        self.cursor.rowcount = 0
        self.assertEqual(get_geneset_hom_ids(1), 0)


if __name__ == '__main__':
    unittest.main()
