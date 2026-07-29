"""
Regression tests for legacy search filter parsing (G3-778).

* getUserFiltersFromApplicationRequest must not raise UnboundLocalError when the
  request carries no 'sortBy' (previously sort_ascending was left unbound and the
  function 500'd).
* buildFilterSelectStatementSetFilters must NOT add an empty IN() filter for an
  unselected facet: an empty tier/species/attribution selection used to match
  nothing and zero the whole result set. An unselected facet must add no filter
  (i.e. "no restriction").

Pure unit tests: geneweaverdb / sphinxapi / config / flask are mocked (no DB, no
search daemon), and apply_user_restrictions is stubbed so only the facet-filter
logic is exercised.  Run from legacy/:  python -m unittest tests.test_search_filters
"""
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


if __name__ == '__main__':
    unittest.main()
