import { ABBA_FIXTURE } from './abba-fixture';
import {
  abbaRunInfo,
  genesCsv,
  geneSymbols,
  occurrenceFraction,
  parseGeneList,
  sortGenesets,
  speciesBarColor,
  speciesCommonName,
  speciesSparkline,
  speciesTile,
  tierLabel,
  tierName,
  tierSparkline,
} from './abba-models';

describe('ABBA models', () => {
  describe('parseGeneList', () => {
    it('splits on lines, commas, semicolons and spaces', () => {
      expect(parseGeneList('Drd2, Drd1\nTh;Slc6a3  Comt')).toEqual(['Drd2', 'Drd1', 'Th', 'Slc6a3', 'Comt']);
    });

    it('drops blanks and case-insensitive repeats, keeping the first spelling', () => {
      expect(parseGeneList(' ,Drd2,,DRD2\n drd2 ,Drd1 ')).toEqual(['Drd2', 'Drd1']);
    });

    it('is empty for an empty field', () => {
      expect(parseGeneList('  \n ')).toEqual([]);
    });
  });

  describe('colours and labels', () => {
    it("uses legacy's seed tile colours by species, ignoring case", () => {
      expect(speciesTile('Mus musculus')).toEqual({ background: '#b3cde3', border: '#4D677D' });
      expect(speciesTile('homo sapiens').background).toBe('#decbe4');
      expect(speciesTile('Danio rerio').background).toBe('#fddaec');
    });

    it('leaves species legacy did not colour white, with a grey border', () => {
      expect(speciesTile('Caenorhabditis elegans')).toEqual({ background: '#ffffff', border: '#8C8C8C' });
      expect(speciesTile(undefined).background).toBe('#ffffff');
    });

    it("gives legacy's short badge names, falling back to the full name", () => {
      expect(speciesCommonName('Homo sapiens')).toBe('Human');
      expect(speciesCommonName('Xenopus tropicalis')).toBe('Xenopus tropicalis');
    });

    it("colours species bars with legacy's hom_colors, by species id", () => {
      expect(speciesBarColor(1)).toBe('#58D87E');
      expect(speciesBarColor(11)).toBe('#698FC6');
      expect(speciesBarColor(99)).toBe('#9CA3AF');
    });

    it("shortens the database's tier names for badges, keeping the full name to hand", () => {
      expect(tierName(2, ABBA_FIXTURE.tiers)).toBe('Tier II - Pro-curated');
      expect(tierLabel(2, ABBA_FIXTURE.tiers)).toBe('Tier II');
      expect(tierLabel(4)).toBe('Tier IV');
      expect(tierLabel(null)).toBe('No tier');
    });
  });

  describe('abbaRunInfo', () => {
    it("reads like legacy's run information panel", () => {
      const rows = Object.fromEntries(abbaRunInfo(ABBA_FIXTURE).map((row) => [row.label, row.value]));
      expect(rows).toEqual({
        'Include homology': 'Yes',
        'Minimum genes': 'Auto',
        'Minimum gene sets': 'Auto',
        'Curation tiers': 'IN (1,2,3)',
        'Restricted to species': 'No',
        'Available genes': (520904).toLocaleString(),
        'Available gene sets': (222413).toLocaleString(),
      });
    });

    it('names restricted species and set thresholds', () => {
      const result = {
        ...ABBA_FIXTURE,
        parameters: { include_homology: false, min_genes: 2, min_genesets: 5, tiers: [3, 1], species_ids: [2, 1] },
      };
      const rows = Object.fromEntries(abbaRunInfo(result).map((row) => [row.label, row.value]));
      expect(rows['Include homology']).toBe('No');
      expect(rows['Minimum genes']).toBe('2');
      expect(rows['Minimum gene sets']).toBe('5');
      expect(rows['Curation tiers']).toBe('IN (1,3)');
      expect(rows['Restricted to species']).toBe('Homo sapiens, Mus musculus');
    });

    it('adds the date only when given one', () => {
      expect(abbaRunInfo(ABBA_FIXTURE).some((row) => row.label === 'Date')).toBe(false);
      expect(abbaRunInfo(ABBA_FIXTURE, new Date(2026, 9, 8)).some((row) => row.label === 'Date')).toBe(true);
    });
  });

  describe('sortGenesets', () => {
    const ids = (sorted: { gs_id: number }[]) => sorted.map((g) => g.gs_id);
    const genesets = ABBA_FIXTURE.genesets;

    it("keeps the API's order (most matches first) for None", () => {
      expect(ids(sortGenesets(genesets, 'none'))).toEqual([282317, 282184, 259156, 265224, 169623, 321618, 241264]);
    });

    it('groups by tier, keeping match order within a tier', () => {
      // The one tier II set, moved to the front, goes back behind the tier I sets.
      const shuffled = [genesets[6], ...genesets.slice(0, 6)];
      expect(ids(sortGenesets(shuffled, 'tier'))).toEqual(ids(genesets));
    });

    it('groups by species name', () => {
      // Danio rerio, Homo sapiens, Mus musculus, Rattus norvegicus.
      expect(ids(sortGenesets(genesets, 'species', ABBA_FIXTURE.species))).toEqual([
        282317, 282184, 241264, 259156, 169623, 265224, 321618,
      ]);
    });

    it('groups by attribution, with none last', () => {
      expect(ids(sortGenesets(genesets, 'attribution'))).toEqual([
        259156, 265224, 321618, 282317, 282184, 241264, 169623,
      ]);
      const unattributed = [{ ...genesets[0], attribution: null }, ...genesets.slice(1)];
      const sorted = ids(sortGenesets(unattributed, 'attribution'));
      expect(sorted[sorted.length - 1]).toBe(282317);
    });

    it('does not reorder its input', () => {
      const input = [...genesets].reverse();
      const copy = [...input];
      sortGenesets(input, 'species', ABBA_FIXTURE.species);
      expect(input).toEqual(copy);
    });
  });

  describe('sparklines', () => {
    const tnf = ABBA_FIXTURE.genes[0];

    it('has one tier bar per tier, scaled to the largest', () => {
      const bars = tierSparkline(tnf, ABBA_FIXTURE.tiers);
      expect(bars.map((bar) => bar.count)).toEqual([2461, 4501, 11, 58, 460]);
      expect(bars[1].height).toBe(1);
      expect(bars[0].height).toBeCloseTo(2461 / 4501);
      expect(bars[0].label).toBe('Tier I - Public Resource');
    });

    it('zero-fills tiers a gene has no gene sets in', () => {
      const gene = { ...tnf, tier_counts: { '1': 12 } };
      expect(tierSparkline(gene).map((bar) => bar.count)).toEqual([12, 0, 0, 0, 0]);
    });

    it('has one species bar per species, in id order, without "All"', () => {
      const bars = speciesSparkline(tnf, ABBA_FIXTURE.species);
      expect(bars.map((bar) => bar.id)).toEqual([1, 2, 3, 4, 5, 6, 8, 9, 10, 11]);
      expect(bars.find((bar) => bar.id === 11)?.count).toBe(9);
      expect(bars.find((bar) => bar.id === 4)?.count).toBe(0);
    });

    it('log-scales species bars, so small counts stay visible', () => {
      const bars = speciesSparkline(tnf, ABBA_FIXTURE.species);
      const human = bars.find((bar) => bar.id === 2)!;
      const dog = bars.find((bar) => bar.id === 11)!;
      expect(human.height).toBe(1);
      expect(dog.height).toBeCloseTo(Math.log10(10) / Math.log10(7565));
      // On a linear scale 9 of 7,564 would be 0.1% of the height; log keeps it at about a quarter.
      expect(dog.height).toBeGreaterThan(0.2);
      expect(bars.find((bar) => bar.id === 4)!.height).toBe(0);
    });
  });

  describe('genes', () => {
    it('fills the occurrence bar against the largest', () => {
      expect(occurrenceFraction(ABBA_FIXTURE.genes[0], 1453)).toBe(1);
      expect(occurrenceFraction(ABBA_FIXTURE.genes[1], 1453)).toBeCloseTo(1385 / 1453);
      expect(occurrenceFraction(ABBA_FIXTURE.genes[1], 0)).toBe(0);
    });

    it('lists every symbol once, preferred first', () => {
      expect(geneSymbols(ABBA_FIXTURE.genes[1])).toEqual(['BDNF', 'ANON2', 'BULN2']);
      expect(geneSymbols({ ...ABBA_FIXTURE.genes[1], symbols: ['ANON2', 'BDNF', 'ANON2'] })).toEqual(['BDNF', 'ANON2']);
    });

    it('writes the chosen genes as CSV, quoting where needed', () => {
      const odd = { ...ABBA_FIXTURE.genes[1], symbol: 'a,"b"', symbols: [], species: 'Danio rerio', occurrences: 12 };
      const csv = genesCsv([ABBA_FIXTURE.genes[0], odd]);
      expect(csv.split('\n')).toEqual([
        'symbol,species,gene_sets,other_symbols',
        'TNF,Homo sapiens,1453,DIF TNF-alpha TNFA TNFSF2 TNLG1F',
        '"a,""b""",Danio rerio,12,',
        '',
      ]);
    });
  });
});
