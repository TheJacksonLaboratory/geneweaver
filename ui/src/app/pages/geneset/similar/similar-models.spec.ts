import {
  groupSimilar,
  radarModel,
  radarPoints,
  similarCsv,
  SimilarGenesetsOutput,
} from './similar-models';

export const SIMILAR: SimilarGenesetsOutput = {
  geneset_id: 5,
  genes: 12,
  thresholds: { threshold: 'none' },
  compared: 15438,
  genesets: [
    { gs_id: 7, name: 'Seven', abbreviation: 'S7', species_id: 2, tier: 3, attribution: null, genes: 13, shared: 12, jaccard: 0.9 },
    { gs_id: 8, name: 'Eight, "quoted"', abbreviation: null, species_id: 1, tier: 1, attribution: 'GWAS', genes: 20, shared: 6, jaccard: 0.3 },
    { gs_id: 9, name: 'Nine', abbreviation: 'N9', species_id: 2, tier: 3, attribution: 'GWAS', genes: 40, shared: 6, jaccard: 0.1 },
    { gs_id: 10, name: 'Ten', abbreviation: 'T', species_id: 3, tier: 5, attribution: null, genes: 9, shared: 2, jaccard: 0.05 },
  ],
  species: { '1': 'Mus musculus', '2': 'Homo sapiens', '3': 'Rattus norvegicus' },
  tiers: { '1': 'Tier I', '3': 'Tier III', '5': 'Tier V' },
};

describe('similar gene sets models', () => {
  it('keeps the list most similar first when not grouped', () => {
    const [only] = groupSimilar(SIMILAR, 'none');
    expect(only.genesets.map((gs) => gs.gs_id)).toEqual([7, 8, 9, 10]);
  });

  it("groups as legacy's grp_by ordered: by the group, then Jaccard", () => {
    expect(groupSimilar(SIMILAR, 'tier').map((g) => [g.label, g.genesets.map((gs) => gs.gs_id)])).toEqual([
      ['Tier I', [8]],
      ['Tier III', [7, 9]],
      ['Tier V', [10]],
    ]);
    expect(groupSimilar(SIMILAR, 'species').map((g) => g.label)).toEqual([
      'Mus musculus',
      'Homo sapiens',
      'Rattus norvegicus',
    ]);
    expect(groupSimilar(SIMILAR, 'attribution').map((g) => g.label)).toEqual(['GWAS', 'No attribution']);
  });

  it('lists a gene set with no tier, last when grouped, and leaves it off the radar', () => {
    const untiered = { ...SIMILAR.genesets[0], gs_id: 11, tier: null };
    const output = { ...SIMILAR, genesets: [...SIMILAR.genesets, untiered] };
    const groups = groupSimilar(output, 'tier');
    expect(groups.at(-1)?.label).toBe('No tier');
    expect(groups.at(-1)?.genesets.map((gs) => gs.gs_id)).toEqual([11]);
    expect(radarModel(output).series.map((s) => s.tier)).toEqual([1, 3, 5]);
    expect(similarCsv(output)).toContain('GS11,Seven,S7,13,12,0.9000,No tier,Homo sapiens');
  });

  it('averages Jaccard per tier and species, zero where a tier has none of a species', () => {
    const radar = radarModel(SIMILAR);
    expect(radar.axes).toEqual(['Mus musculus', 'Homo sapiens', 'Rattus norvegicus']);
    const tier3 = radar.series.find((s) => s.tier === 3) ?? radar.series[0];
    expect(tier3.values[0]).toBe(0);
    expect(tier3.values[1]).toBeCloseTo(0.5);
    expect(tier3.count).toBe(2);
    expect(radar.max).toBeCloseTo(0.5);
  });

  it('puts a full value on the axis end, the first axis straight up', () => {
    expect(radarPoints([1, 0, 0, 0], 1, 100).split(' ')[0]).toBe('0.0,-100.0');
  });

  it("exports legacy's columns, quoting what needs it", () => {
    const lines = similarCsv(SIMILAR).trim().split('\n');
    expect(lines[0]).toBe('gs_id,name,abbreviation,genes,shared,jaccard,tier,species');
    expect(lines[1]).toBe('GS7,Seven,S7,13,12,0.9000,Tier III,Homo sapiens');
    expect(lines[2]).toContain('"Eight, ""quoted"""');
  });
});
