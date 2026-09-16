"""
Regression tests for /findPublications -- "Find other GeneSets from this publication"
(G3-825).

`get_similar_genesets_by_publication` shipped in 2015 (`ffd24d80`) with four defects it
kept for eleven years, unchanged in substance. Measured against geneweaver-prod:

* It asked `geneset_is_readable2` one round trip per sibling gene set. For the GO
  Consortium paper (PMID 10802651, 14,799 gene sets) that was 18.62 s, 1.26 ms a call.
  The same predicate evaluated inside the query costs ~13 us a row: 0.198 s in total.
* It then **discarded those answers** -- `gs_ids_clean` was built and never read, and
  the final query used the unfiltered list. So the 18.62 s bought nothing, and on the
  170 prod publications that mix readable and non-readable gene sets the route returned
  metadata for gene sets the check had already rejected.
* It interpolated the id list into `IN (%s)`, so a gene set with no publication --
  154,651 of prod's -- produced `IN ()`, a SyntaxError, an unconditional HTTP 500.
  Caught in prod's log on 2026-09-13, before 1.6.0 shipped.
* That interpolation is also the pattern CLAUDE.md prohibits outright.

Rendering every sibling was a *second* N+1: each row becomes a Geneset, and
Geneset.__init__ calls get_all_publications(), its own query at 0.91 ms -- another
13.5 s for that publication. Hence a bounded page, not only better SQL.

The DB tests run with no database: geneweaverdb builds a connection pool at import, so
a fake psycopg2 is installed whose pool never connects and PooledCursor is patched to
feed canned rows. The route is asserted on the parsed AST, matching
tests/test_search_filters.py -- src/application.py builds the Flask app at import and
cannot be loaded in a pure unit test.

Run from legacy/:  python -m unittest tests.db.test_find_publications
"""
import ast
import os
import re
import sys
import types
import unittest
from unittest.mock import patch, MagicMock


def _install_import_shims():
    """Make `import src.geneweaverdb` succeed with no DB / no psycopg2 installed."""
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

    for name in ('config', 'notifications', 'pubmedsvc', 'annotator',
                 'curation_assignments', 'flask', 'tools', 'tools.toolcommon'):
        sys.modules.setdefault(name, MagicMock())


_install_import_shims()
from src import geneweaverdb  # noqa: E402
from src.geneweaverdb import (  # noqa: E402
    SIMILAR_BY_PUBLICATION_PAGE_SIZE,
    count_similar_genesets_by_publication,
    get_similar_genesets_by_publication,
)

_LEGACY = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _squash(sql):
    """Collapse whitespace so multi-line SQL can be matched as one string."""
    return re.sub(r'\s+', ' ', sql).strip()


class SimilarByPublicationQueryTests(unittest.TestCase):
    """What the two queries must and must not contain."""

    def setUp(self):
        self.patcher = patch('src.geneweaverdb.PooledCursor')
        mock_pc = self.patcher.start()
        self.cursor = MagicMock()
        mock_pc.return_value.__enter__.return_value = self.cursor
        # Geneset construction is not under test here; it needs a whole gene set row
        # and would fan out into publication lookups.
        self.geneset_patcher = patch('src.geneweaverdb.Geneset', side_effect=lambda d: d)
        self.geneset_patcher.start()
        self.dictify_patcher = patch('src.geneweaverdb.dictify_cursor',
                                     side_effect=lambda c: self.rows)
        self.dictify_patcher.start()
        self.rows = []

    def tearDown(self):
        self.dictify_patcher.stop()
        self.geneset_patcher.stop()
        self.patcher.stop()

    def _call(self, **kwargs):
        kwargs.setdefault('geneset_id', 374128)
        kwargs.setdefault('user_id', 0)
        return get_similar_genesets_by_publication(**kwargs)

    def _sql(self):
        return _squash(self.cursor.execute.call_args[0][0])

    def _params(self):
        return self.cursor.execute.call_args[0][1]

    # --- the N+1 and the discarded filter ------------------------------------
    def test_one_statement_not_one_per_sibling(self):
        self.rows = [{'gs_id': 1}, {'gs_id': 2}, {'gs_id': 3}]
        self._call()
        self.assertEqual(
            self.cursor.execute.call_count, 1,
            'one query per page, not one per sibling gene set: the old loop cost '
            '18.62 s on a 14,799-gene-set publication (G3-825)')

    def test_readability_is_part_of_the_query(self):
        self._call()
        self.assertIn('geneset_is_readable2', self._sql(),
                      'the permission check must be applied by the query, not '
                      'computed in Python and then discarded (G3-825)')

    def test_count_query_applies_the_same_predicate(self):
        self.cursor.fetchone.return_value = (14799,)
        count_similar_genesets_by_publication(374128, 0)
        sql = _squash(self.cursor.execute.call_args[0][0])
        self.assertIn('geneset_is_readable2', sql,
                      'the total must count only readable gene sets, or the page '
                      'count disagrees with the pages')
        self.assertIn('count(*)', sql)

    def test_count_returns_the_scalar(self):
        self.cursor.fetchone.return_value = (14799,)
        self.assertEqual(count_similar_genesets_by_publication(374128, 0), 14799)

    # --- the IN () crash -----------------------------------------------------
    def test_publication_is_matched_by_equality_not_in(self):
        self._call()
        sql = self._sql()
        self.assertRegex(
            sql, r'g\.pub_id\s*=\s*\(\s*SELECT pub_id',
            'must compare pub_id to a scalar subquery: `IN (SELECT ...)` with a NULL '
            'publication left an empty Python list that interpolated to `IN ()` -- a '
            'SyntaxError and an unconditional 500 (G3-825)')

    def test_no_id_list_is_interpolated_into_the_sql(self):
        self._call()
        sql = self.cursor.execute.call_args[0][0]
        self.assertNotIn('IN ()', sql)
        self.assertFalse(
            re.search(r'IN\s*\(\s*%s\s*\)', sql),
            'no `IN (%s)` id list: CLAUDE.md prohibits %%-interpolating a query string')
        self.cursor.mogrify.assert_not_called()

    def test_no_rows_is_an_empty_list_not_an_error(self):
        self.rows = []
        self.assertEqual(self._call(), [])

    # --- parameter binding ---------------------------------------------------
    def test_all_values_are_bound(self):
        self._call(limit=25, offset=50)
        params = self._params()
        self.assertEqual(params['gs_id'], 374128)
        self.assertEqual(params['limit'], 25)
        self.assertEqual(params['offset'], 50)

    def test_anonymous_caller_becomes_minus_one(self):
        self._call(user_id=0)
        self.assertEqual(self._params()['user_id'], -1,
                         'geneset_is_readable2 expects -1 for the anonymous caller')

    def test_a_real_user_id_is_passed_through(self):
        self._call(user_id=25849012)
        self.assertEqual(self._params()['user_id'], 25849012)

    def test_count_maps_the_anonymous_caller_the_same_way(self):
        self.cursor.fetchone.return_value = (0,)
        count_similar_genesets_by_publication(374128, 0)
        self.assertEqual(self.cursor.execute.call_args[0][1]['user_id'], -1)

    # --- the page bound ------------------------------------------------------
    def test_query_is_bounded_and_ordered(self):
        self._call()
        sql = self._sql()
        self.assertIn('LIMIT %(limit)s', sql)
        self.assertIn('OFFSET %(offset)s', sql)
        self.assertIn('ORDER BY g.gs_id', sql,
                      'paging without a total order repeats and skips rows')

    def test_default_page_size_is_bounded(self):
        self._call()
        self.assertEqual(self._params()['limit'], SIMILAR_BY_PUBLICATION_PAGE_SIZE)
        self.assertLessEqual(
            SIMILAR_BY_PUBLICATION_PAGE_SIZE, 500,
            'each row costs a get_all_publications() query inside Geneset.__init__ '
            '(0.91 ms on prod), so the page size is what bounds this route')


class FindPublicationsRouteTests(unittest.TestCase):
    """The route, asserted on the AST.

    src/application.py builds the Flask app at import and pulls in a long tail of
    packages, so it cannot be imported in a pure unit test -- same approach as
    tests/test_search_filters.py.
    """

    SOURCE = os.path.join(_LEGACY, 'src', 'application.py')

    @classmethod
    def setUpClass(cls):
        with open(cls.SOURCE) as fh:
            cls.src = fh.read()
        cls.functions = {n.name: n for n in ast.walk(ast.parse(cls.src))
                         if isinstance(n, ast.FunctionDef)}
        cls.view = cls.functions.get('render_view_same_publications')

    def _segment(self):
        return ast.get_source_segment(self.src, self.view) or ''

    def test_view_still_exists(self):
        self.assertIsNotNone(self.view, 'render_view_same_publications no longer exists')

    def test_view_asks_for_a_bounded_page(self):
        seg = self._segment()
        self.assertIn('limit=', seg)
        self.assertIn('offset=', seg,
                      'the view must page, or one request renders every gene set '
                      'sharing the publication (G3-825)')

    def test_view_fetches_a_total_for_the_pager(self):
        self.assertIn('count_similar_genesets_by_publication', self._segment())

    def test_view_passes_the_total_to_the_template(self):
        seg = self._segment()
        self.assertIn('total=', seg,
                      "the template's empty state keys off the total; without it a "
                      'last page holding one row reads as "no other GeneSets"')

    def test_view_tolerates_a_junk_page_argument(self):
        seg = self._segment()
        self.assertTrue(
            re.search(r'except\s*\(?[^)]*ValueError', seg),
            '/findPublications/1?page=abc must fall back to page 1, not 500')


class ViewSamePublicationsTemplateTests(unittest.TestCase):
    """The template contract the view depends on."""

    TEMPLATE = os.path.join(_LEGACY, 'src', 'templates', 'viewsamepublications.html')

    @classmethod
    def setUpClass(cls):
        with open(cls.TEMPLATE) as fh:
            cls.html = fh.read()

    def test_empty_state_keys_off_the_total(self):
        self.assertRegex(
            self.html, r'{%\s*if\s+total\s+is\s+not\s+defined\s+or\s+total\s*<\s*2\s*%}',
            'the empty state must test the total, not this page\'s length')

    def test_empty_state_message_is_kept(self):
        self.assertIn('There are no other GeneSets annotated to the same publication',
                      self.html)

    def test_pager_is_rendered_only_when_there_is_more_than_one_page(self):
        self.assertRegex(self.html, r'{%\s*if\s+num_pages\s+is\s+defined\s+and\s+num_pages\s*>\s*1\s*%}')

    def test_pager_links_carry_the_page_number(self):
        self.assertIn('/findPublications/{{ gs_id }}?page={{ page + 1 }}', self.html)
        self.assertIn('/findPublications/{{ gs_id }}?page={{ page - 1 }}', self.html)


if __name__ == '__main__':
    unittest.main()
