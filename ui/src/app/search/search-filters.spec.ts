import {
  activeFilterCount,
  canSearch,
  describeMatches,
  describeSearch,
  emptyFilters,
  filterProblem,
  fromQueryParams,
  MAX_GENES,
  parseGenes,
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

    it('sends one gene as before, with homologs by default (G3-834)', () => {
      const params = searchParams('', filters({ gene: 'Drd2' }), page);
      expect(params.getAll('gene')).toEqual(['Drd2']);
      expect(params.has('gene_match')).toBe(false);
      expect(params.has('homology')).toBe(false); // The API's default: on.
    });

    it('sends several genes, all or any, and homology only when switched off (G3-832)', () => {
      const all = searchParams('', filters({ gene: 'Drd2, Tp53', pValue: 0.05 }), page);
      expect(all.getAll('gene')).toEqual(['Drd2', 'Tp53']);
      expect(all.get('gene_match')).toBe('all');
      expect(all.get('p_value')).toBe('0.05');
      const any = searchParams('', filters({ gene: 'Drd2 OR Th', homology: false }), page);
      expect(any.getAll('gene')).toEqual(['Drd2', 'Th']);
      expect(any.get('gene_match')).toBe('any');
      expect(any.get('homology')).toBe('false');
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

  describe('parseGenes (G3-832)', () => {
    it.each([
      ['Drd2', ['Drd2'], 'all'],
      ['Drd2, Tp53', ['Drd2', 'Tp53'], 'all'],
      ['Drd2 Tp53', ['Drd2', 'Tp53'], 'all'],
      ['Drd2 AND Tp53', ['Drd2', 'Tp53'], 'all'],
      ['Drd2 OR Th OR Tp53', ['Drd2', 'Th', 'Tp53'], 'any'],
      [' drd2, Drd2 ;Tp53 ', ['drd2', 'Tp53'], 'all'],
    ])('reads %p as %p, %p', (text, genes, match) => {
      expect(parseGenes(text)).toEqual({ genes, match });
    });

    it('treats lower-case and/or as genes, as the text search does', () => {
      expect(parseGenes('Drd2 or Th').genes).toEqual(['Drd2', 'or', 'Th']);
    });

    it('refuses AND with OR, and too many genes', () => {
      expect(parseGenes('Drd2 AND Tp53 OR Th').error).toContain('not both');
      const many = Array.from({ length: MAX_GENES + 1 }, (_, i) => `G${i}`).join(' ');
      expect(parseGenes(many).error).toContain(`At most ${MAX_GENES}`);
    });
  });

  it.each([
    [filters({ gene: 'Drd2 AND Tp53 OR Th' }), 'not both'],
    [filters({ sizeMin: 10, sizeMax: 5 }), 'smallest size'],
    [filters({ gene: 'Drd2', effectLow: 2, effectHigh: 1 }), 'effect'],
    [filters({ pValue: 0.05 }), 'enter one'],
  ])('says what is wrong with %o', (value, message) => {
    expect(filterProblem(value)).toContain(message);
  });

  it('round-trips through the URL, clearing what is unset', () => {
    const value = filters({
      species: [1, 2],
      tiers: [3],
      gene: 'Drd2 OR Th',
      homology: false,
      pValue: 0.01,
      thresholdMode: 'first',
    });
    const sort = { by: 'name' as const, order: 'desc' as const };
    const params = toQueryParams(value, sort);
    expect(params['score']).toBeNull();
    expect(params['homology']).toBe('off');
    expect(toQueryParams(emptyFilters(), sort)['homology']).toBeNull(); // On is the default.
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

  describe('describeSearch', () => {
    it('says text results are gene sets matched by their text', () => {
      expect(describeSearch(' alcohol ', emptyFilters())).toBe(
        'Gene sets whose name, description, publication, ontology terms or genes match "alcohol"',
      );
    });

    it('says gene results are gene sets that contain the gene, or a homolog by default', () => {
      expect(describeSearch('', filters({ gene: ' Drd2 ' }))).toBe('Gene sets that contain Drd2 (or a homolog)');
      expect(describeSearch('', filters({ gene: 'Drd2', homology: false }))).toBe('Gene sets that contain Drd2');
    });

    it('names several genes, all or any (G3-832)', () => {
      expect(describeSearch('', filters({ gene: 'Drd2, Tp53, Th', homology: false }))).toBe(
        'Gene sets that contain Drd2, Tp53 and Th',
      );
      expect(describeSearch('', filters({ gene: 'Drd2 OR Th' }))).toBe(
        'Gene sets that contain Drd2 or Th (or their homologs)',
      );
      const cut = filters({ gene: 'Drd2 Tp53', homology: false, pValue: 0.05 });
      expect(describeSearch('', cut)).toBe("Gene sets that contain Drd2 and Tp53 with each gene's p-value ≤ 0.05");
      expect(describeSearch('', { ...cut, thresholdMode: 'first' })).toBe(
        'Gene sets that contain Drd2 and Tp53, those where the most of them have p-value ≤ 0.05 first',
      );
    });

    it('names the cutoffs, and whether they filter or only order', () => {
      const cut = filters({ gene: 'Drd2', homology: false, pValue: 0.05, correlationLow: 0.3 });
      expect(describeSearch('', cut)).toBe('Gene sets that contain Drd2 with p-value ≤ 0.05 or correlation ≥ 0.3');
      expect(describeSearch('', { ...cut, thresholdMode: 'first' })).toBe(
        'Gene sets that contain Drd2, those where its p-value ≤ 0.05 or correlation ≥ 0.3 first',
      );
    });

    it('joins text and gene, and is empty with neither', () => {
      expect(describeSearch('alcohol', filters({ gene: 'Drd2', homology: false }))).toBe(
        'Gene sets whose name, description, publication, ontology terms or genes match "alcohol", and that contain Drd2',
      );
      expect(describeSearch(' ', emptyFilters())).toBe('');
    });
  });

  it('says which gene each result matched, naming homologs (G3-834)', () => {
    expect(
      describeMatches([
        { query: 'TP53', gene: 'Trp53', homolog: true, value: 0.01 },
        { query: 'Drd2', gene: 'Drd2', homolog: false },
      ]),
    ).toBe('Trp53 (homolog of TP53), Drd2');
    expect(describeMatches(undefined)).toBe('');
  });
});
