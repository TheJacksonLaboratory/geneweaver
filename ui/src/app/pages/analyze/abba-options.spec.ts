import {
  ABBA_MAX_GENES,
  abbaCanRun,
  abbaProblem,
  abbaRequestBody,
  defaultAbbaOptions,
  MIN_GENESETS_CHOICES,
  minGenesChoices,
  toggled,
} from './abba-options';

describe('ABBA options', () => {
  it("defaults to legacy's: homology, Auto, tiers 1-3, all species", () => {
    expect(defaultAbbaOptions()).toEqual({
      includeHomology: true,
      minGenes: null,
      minGenesets: null,
      tiers: [1, 2, 3],
      restrictSpecies: false,
      speciesIds: [],
    });
  });

  it('offers Auto and 1-50 minimum gene sets', () => {
    expect(MIN_GENESETS_CHOICES[0]).toBeNull();
    expect(MIN_GENESETS_CHOICES.slice(1)).toEqual(Array.from({ length: 50 }, (_, i) => i + 1));
  });

  it('offers one minimum-genes choice per seed gene, capped at 50, or 1-50 with none typed', () => {
    expect(minGenesChoices(3)).toEqual([null, 1, 2, 3]);
    expect(minGenesChoices(200)).toHaveLength(51);
    expect(minGenesChoices(0)).toHaveLength(51);
  });

  it('toggles an id in and out, keeping the list sorted', () => {
    expect(toggled([1, 3], 2)).toEqual([1, 2, 3]);
    expect(toggled([1, 2, 3], 2)).toEqual([1, 3]);
  });

  it('runs with genes or gene sets, and not with neither', () => {
    const options = defaultAbbaOptions();
    expect(abbaCanRun([], [], options)).toBe(false);
    expect(abbaCanRun(['Drd2'], [], options)).toBe(true);
    expect(abbaCanRun([], [167180], options)).toBe(true);
  });

  it('names what is wrong', () => {
    const options = defaultAbbaOptions();
    const tooMany = Array.from({ length: ABBA_MAX_GENES + 1 }, (_, i) => `G${i}`);
    expect(abbaProblem(tooMany, [], options)).toContain(`at most ${ABBA_MAX_GENES} seed genes`);
    expect(abbaProblem(['Drd2'], Array.from({ length: 21 }, (_, i) => i + 1), options)).toContain('at most 20');
    expect(abbaProblem(['Drd2'], [], { ...options, tiers: [] })).toBe('Choose at least one curation tier.');
    expect(abbaProblem(['Drd2'], [], { ...options, restrictSpecies: true })).toContain('at least one species');
    expect(abbaProblem(['Drd2'], [], options)).toBeUndefined();
  });

  it('sends null species when not restricted, even if some were ticked earlier', () => {
    const options = { ...defaultAbbaOptions(), speciesIds: [2] };
    expect(abbaRequestBody(['Drd2'], [], options).species_ids).toBeNull();
    expect(abbaRequestBody(['Drd2'], [], { ...options, restrictSpecies: true, speciesIds: [2, 1] }).species_ids).toEqual([1, 2]);
  });
});
