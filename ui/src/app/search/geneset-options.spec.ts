import { appendPage, parseIds, toOption } from './geneset-options';

describe('gene set search options', () => {
  describe('parseIds', () => {
    it.each([
      ['514', [514]],
      ['514, 515', [514, 515]],
      ['GS514 gs515;516', [514, 515, 516]],
      ['  514,,515  ', [514, 515]],
    ])('reads %p as ids', (text, ids) => {
      expect(parseIds(text)).toEqual(ids);
    });

    it.each(['', '   ', 'dopamine', '514 dopamine', 'GS', '0', '-5', '1.5'])(
      'treats %p as a search, not ids',
      (text) => {
        expect(parseIds(text)).toBeUndefined();
      },
    );
  });

  describe('toOption', () => {
    it('labels the chip by id and abbreviation, and describes the gene set', () => {
      const option = toOption({
        id: 167180,
        abbreviation: 'MP:0009747',
        name: 'impaired behavioral response',
        species_id: 1,
        curation_id: 3,
        score_type: 1,
        count: 1234,
      });
      expect(option).toEqual({
        id: 167180,
        chip: 'GS167180 · MP:0009747',
        abbreviation: 'MP:0009747',
        detail: `Mus musculus · Tier III · p-value · ${(1234).toLocaleString()} genes`,
      });
    });

    it('falls back to the name, then to the id alone', () => {
      expect(toOption({ id: 5, name: 'A name' }).chip).toBe('GS5 · A name');
      expect(toOption({ id: 5 })).toEqual({ id: 5, chip: 'GS5', abbreviation: undefined, detail: undefined });
    });
  });

  it('appends a page without repeating rows already listed', () => {
    const page = (...ids: number[]) => ids.map((id) => toOption({ id }));
    expect(appendPage(page(1, 2), page(2, 3, 3)).map((option) => option.id)).toEqual([1, 2, 3]);
  });
});
