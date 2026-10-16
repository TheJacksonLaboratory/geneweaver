import {
  activeFilterCount,
  canSearch,
  emptyFilters,
  filterProblem,
  fromQueryParams,
  searchParams,
  SearchFilters,
  speciesName,
  toQueryParams,
} from './search-filters';

const page = { offset: 0, limit: 25 };
const filters = (changes: Partial<SearchFilters>): SearchFilters => ({ ...emptyFilters(), ...changes });

describe('search filters', () => {
  describe('searchParams', () => {
    it('sends text and paging alone when no filter is set', () => {
      const params = searchParams(' dopamine ', emptyFilters(), page);
      expect(params.keys().sort()).toEqual(['limit', 'offset', 'search_text']);
      expect(params.get('search_text')).toBe('dopamine');
    });

    it("combines filters, by the API's own names (G3-777)", () => {
      const params = searchParams(
        'dopamine',
        filters({ species: [1, 8], tiers: [2, 3], scoreTypes: [1], sizeMin: 10, sizeMax: 500 }),
        page,
        { by: 'size', order: 'desc' },
      );
      expect(params.getAll('species')).toEqual(['Mus Musculus', 'Caenorhabditis Elegans']);
      expect(params.getAll('curation_tier')).toEqual(['Tier II', 'Tier III']);
      expect(params.getAll('score_type')).toEqual(['p-value']);
      expect(params.get('gte_count')).toBe('10');
      expect(params.get('lte_count')).toBe('500');
      expect(params.get('sort_by')).toBe('size');
      expect(params.get('sort_order')).toBe('desc');
    });

    it('sends a gene with its cutoffs and mode (G3-764), and a gene alone is a search', () => {
      const params = searchParams(
        '',
        filters({ gene: ' Drd2 ', pValue: 0.01, correlationLow: 0.5, thresholdMode: 'first' }),
        page,
      );
      expect(params.has('search_text')).toBe(false);
      expect(params.get('gene')).toBe('Drd2');
      expect(params.get('p_value')).toBe('0.01');
      expect(params.get('correlation_low')).toBe('0.5');
      expect(params.has('correlation_high')).toBe(false);
      expect(params.get('threshold_mode')).toBe('first');
    });

    it('leaves cutoffs out without a gene, since the API refuses them alone', () => {
      const params = searchParams('x', filters({ pValue: 0.01 }), page);
      expect(params.has('p_value')).toBe(false);
      expect(params.has('threshold_mode')).toBe(false);
    });
  });

  it('counts the filters set, a gene and its cutoffs separately', () => {
    expect(activeFilterCount(emptyFilters())).toBe(0);
    expect(activeFilterCount(filters({ species: [1], sizeMax: 5, gene: 'Drd2', qValue: 0.1 }))).toBe(4);
  });

  it('can search with text or a gene', () => {
    expect(canSearch('', emptyFilters())).toBe(false);
    expect(canSearch('  ', filters({ gene: 'Drd2' }))).toBe(true);
    expect(canSearch('dopamine', emptyFilters())).toBe(true);
  });

  it.each([
    [filters({ sizeMin: 10, sizeMax: 5 }), 'smallest size'],
    [filters({ gene: 'Drd2', effectLow: 2, effectHigh: 1 }), 'effect'],
    [filters({ pValue: 0.05 }), 'enter one'],
  ])('says what is wrong with %o', (value, message) => {
    expect(filterProblem(value)).toContain(message);
  });

  it('round-trips through the URL, clearing what is unset', () => {
    const value = filters({ species: [1, 2], tiers: [3], gene: 'Drd2', pValue: 0.01, thresholdMode: 'first' });
    const sort = { by: 'name' as const, order: 'desc' as const };
    const params = toQueryParams(value, sort);
    expect(params['score']).toBeNull();
    const defined = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== null),
    ) as Record<string, string>;
    expect(fromQueryParams(defined)).toEqual({ filters: value, sort });
  });

  it('ignores what it cannot read in the URL', () => {
    const { filters: read, sort } = fromQueryParams({ species: '1,x,-2', p: 'abc', sort: 'gs_name' });
    expect(read.species).toEqual([1]);
    expect(read.pValue).toBeNull();
    expect(sort.by).toBeNull();
  });

  it('names species by id, including ids above the gap at 7', () => {
    expect(speciesName(8)).toBe('Caenorhabditis elegans');
    expect(speciesName(99)).toBe('Species 99');
  });
});
