"""
Regression tests for legacy search filter parsing (G3-778).

* getUserFiltersFromApplicationRequest must not raise UnboundLocalError when the
  request carries no 'sortBy' (previously sort_ascending was left unbound and the
  function 500'd).
* buildFilterSelectStatementSetFilters must NOT add an empty IN() filter for an
  unselected facet: an empty tier/species/attribution selection used to match
  nothing and zero the whole result set. An unselected facet must add no filter
  (i.e. "no restriction").
* render_search_json must check STATUS before indexing search_values. On a
  no-match or errored search, keyword_paginated_search returns ONLY a STATUS key,
  so reading search_values['searchresults'] raised KeyError -> HTTP 500 from
  /searchFilter.json. (The third of the three G3-778 bugs; the two above were
  covered from the start, this one was not.)

Pure unit tests: geneweaverdb / sphinxapi / config / flask are mocked (no DB, no
search daemon), and apply_user_restrictions is stubbed so only the facet-filter
logic is exercised.  Run from legacy/:  python -m unittest tests.test_search_filters
"""
import ast
import os
import sys
import unittest
from unittest.mock import MagicMock

# search.py reads the sphinx host/port from config at import and imports these.
sys.modules['geneweaverdb'] = MagicMock()
sys.modules['sphinxapi'] = MagicMock()
sys.modules['config'] = MagicMock()
sys.modules['flask'] = MagicMock()

import src.search as search

SPECIES = {1: 'Mus musculus', 2: 'Homo sapiens', 3: 'Rattus norvegicus'}
ATTRIBS = {10: 'GWAS', 11: 'KEGG'}


class RecordingSphinxClient:
    """Minimal fake Sphinx client that records filter calls."""

    def __init__(self):
        self.filters = []   # (attr, values, exclude)
        self.ranges = []    # (attr, min, max)

    def SetFilter(self, attr, values, exclude=False):
        self.filters.append((attr, list(values), exclude))

    def SetFilterRange(self, attr, mn, mx):
        self.ranges.append((attr, mn, mx))

    # apply_user_restrictions is stubbed out in tests, but keep these harmless.
    def SetSelect(self, *a, **k):
        pass


def _form(**overrides):
    f = {'searchbar': 'brain', 'pagination_page': '1', 'searchGenesets': 'on'}
    f.update(overrides)
    return f


class GetUserFiltersSortTests(unittest.TestCase):
    def setUp(self):
        search.geneweaverdb.get_all_species = MagicMock(return_value=dict(SPECIES))
        search.geneweaverdb.get_all_attributions = MagicMock(return_value=dict(ATTRIBS))

    def test_no_sortby_does_not_raise(self):
        # G3-778 fix #2: previously raised UnboundLocalError on sort_ascending.
        result = search.getUserFiltersFromApplicationRequest(_form())
        self.assertIsNone(result['sort_by'])
        self.assertIsNone(result['sort_ascending'])

    def test_sortby_species_ascending(self):
        result = search.getUserFiltersFromApplicationRequest(
            _form(sortBy='species', sortAscending='true'))
        self.assertEqual(result['sort_by'], 'species')
        self.assertTrue(result['sort_ascending'])

    def test_sortby_descending(self):
        result = search.getUserFiltersFromApplicationRequest(
            _form(sortBy='tier', sortAscending='false'))
        self.assertEqual(result['sort_by'], 'tier')
        self.assertFalse(result['sort_ascending'])


class BuildFilterEmptyFacetTests(unittest.TestCase):
    def setUp(self):
        search.geneweaverdb.get_all_species = MagicMock(return_value=dict(SPECIES))
        search.geneweaverdb.get_all_attributions = MagicMock(return_value=dict(ATTRIBS))
        # Isolate the facet-filter logic from the (flask/DB-backed) visibility
        # restriction, which is not under test here.
        self._orig_restrict = search.apply_user_restrictions
        search.apply_user_restrictions = lambda *a, **k: None

    def tearDown(self):
        search.apply_user_restrictions = self._orig_restrict

    def _uf(self, tiers=None, species=None, attribs=None):
        tiers, species, attribs = tiers or {}, species or {}, attribs or {}
        return {
            'statusList': {'provisional': 'no', 'deprecated': 'no'},
            'tierList': {k: ('yes' if tiers.get(k) else 'no')
                         for k in ('noTier', 'tier1', 'tier2', 'tier3', 'tier4', 'tier5')},
            'speciesList': {'sp%d' % sid: ('yes' if species.get(sid) else 'no')
                            for sid in SPECIES},
            'attributionsList': dict(
                {'at%d' % aid: ('yes' if attribs.get(aid) else 'no') for aid in ATTRIBS},
                at0='no'),
            'geneCounts': {'geneCountMin': '0', 'geneCountMax': '1000'},
        }

    def _attrs(self, client):
        return {f[0] for f in client.filters}

    def test_no_facets_selected_adds_no_facet_filters(self):
        # G3-778 fix #3: empty tier/species/attribution selections must not add
        # empty IN() filters (which match nothing and zero the result set).
        client = RecordingSphinxClient()
        search.buildFilterSelectStatementSetFilters(self._uf(), client)
        attrs = self._attrs(client)
        self.assertNotIn('cur_id', attrs)
        self.assertNotIn('sp_id', attrs)
        self.assertNotIn('attribution', attrs)

    def test_selected_tier_adds_cur_id_filter(self):
        client = RecordingSphinxClient()
        search.buildFilterSelectStatementSetFilters(self._uf(tiers={'tier3': True}), client)
        cur = [f for f in client.filters if f[0] == 'cur_id']
        self.assertEqual(len(cur), 1)
        self.assertIn(3, cur[0][1])

    def test_selected_species_adds_sp_id_filter(self):
        client = RecordingSphinxClient()
        search.buildFilterSelectStatementSetFilters(self._uf(species={2: True}), client)
        sp = [f for f in client.filters if f[0] == 'sp_id']
        self.assertEqual(len(sp), 1)
        self.assertIn(2, sp[0][1])

    def test_selected_attribution_adds_attribution_filter(self):
        client = RecordingSphinxClient()
        search.buildFilterSelectStatementSetFilters(self._uf(attribs={10: True}), client)
        at = [f for f in client.filters if f[0] == 'attribution']
        self.assertEqual(len(at), 1)
        self.assertIn(10, at[0][1])


class SearchNoResultsGuardTests(unittest.TestCase):
    """The zero-result guard in application.py's two search render paths.

    These are asserted structurally, on the parsed AST, rather than by calling the
    views. src/application.py is 6,330 lines with 59 top-level imports (flask_admin
    among them) and builds the Flask app at import, so it cannot be imported in a
    pure unit test without mocking a long and brittle tail of packages. What
    actually broke was control flow -- an unguarded subscript -- and that is
    checkable directly: the STATUS guard must appear, must return, and must come
    before anything reads search_values['searchresults'].
    """

    SOURCE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'src', 'application.py')

    @classmethod
    def setUpClass(cls):
        with open(cls.SOURCE) as fh:
            cls.src = fh.read()
        cls.functions = {n.name: n for n in ast.walk(ast.parse(cls.src))
                         if isinstance(n, ast.FunctionDef)}

    def _segment(self, node):
        return ast.get_source_segment(self.src, node) or ''

    def _guard_line(self, func):
        """First line of an `if ... STATUS ...:` that returns out of the function."""
        lines = [n.lineno for n in ast.walk(func)
                 if isinstance(n, ast.If)
                 and 'STATUS' in self._segment(n.test)
                 and any(isinstance(c, ast.Return) for c in ast.walk(n))]
        return min(lines) if lines else None

    def _searchresults_line(self, func):
        """First line that subscripts search_values with 'searchresults'."""
        lines = []
        for n in ast.walk(func):
            if isinstance(n, ast.Subscript):
                seg = self._segment(n).replace('"', "'")
                if seg.startswith('search_values[') and "'searchresults'" in seg:
                    lines.append(n.lineno)
        return min(lines) if lines else None

    def _assert_guarded(self, name):
        self.assertIn(name, self.functions, '%s no longer exists' % name)
        func = self.functions[name]
        guard = self._guard_line(func)
        access = self._searchresults_line(func)
        self.assertIsNotNone(
            guard,
            '%s has no STATUS check that returns early; a no-match search will '
            'KeyError on search_values and 500 (G3-778)' % name)
        self.assertIsNotNone(access, '%s no longer reads searchresults' % name)
        self.assertLess(
            guard, access,
            '%s reads search_values[\'searchresults\'] at line %s before its STATUS '
            'guard at line %s -- a no-match search 500s (G3-778)' % (name, access, guard))

    def test_search_json_guards_no_matches_before_reading_results(self):
        # /searchFilter.json -- the bug. Every filter change, sort and page click
        # goes through here, so an unguarded no-match search 500s the whole page.
        self._assert_guarded('render_search_json')

    def test_search_page_guards_no_matches_before_reading_results(self):
        # /search/ -- already guarded; the json route was fixed to mirror it.
        # Locked in so the pair cannot drift apart again.
        self._assert_guarded('render_searchFromHome')


if __name__ == '__main__':
    unittest.main()
