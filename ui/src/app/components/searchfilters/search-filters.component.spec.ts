import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';

import { SearchFiltersComponent } from './search-filters.component';
import { emptyFilters, FILTER_HELP } from '../../search/search-filters';

describe('SearchFiltersComponent info icons', () => {
  let fixture: ComponentFixture<SearchFiltersComponent>;

  const render = async (gene = '') => {
    await TestBed.configureTestingModule({
      imports: [SearchFiltersComponent, NoopAnimationsModule],
    }).compileComponents();
    fixture = TestBed.createComponent(SearchFiltersComponent);
    fixture.componentRef.setInput('filters', { ...emptyFilters(), gene });
    fixture.detectChanges();
  };

  const tips = (): string[] =>
    Array.from(fixture.nativeElement.querySelectorAll('.info-tip') as NodeListOf<HTMLElement>).map(
      (icon) => icon.getAttribute('aria-label') ?? '',
    );

  it('explains each filter shown without a gene', async () => {
    await render();
    expect(tips()).toEqual([
      `Species: ${FILTER_HELP.species}`,
      `Curation tier: ${FILTER_HELP.tier}`,
      `Score type: ${FILTER_HELP.scoreType}`,
      `Gene set size, min: ${FILTER_HELP.sizeMin}`,
      `Gene set size, max: ${FILTER_HELP.sizeMax}`,
      `Genes: ${FILTER_HELP.gene}`,
      `Include homologs in other species: ${FILTER_HELP.homology}`,
    ]);
  });

  it('explains the score cutoffs and both ways of using them once a gene is typed', async () => {
    await render('Drd2');
    const shown = tips();
    expect(shown).toHaveLength(14);
    expect(shown).toEqual(
      expect.arrayContaining([
        `Score cutoffs: ${FILTER_HELP.cutoffs}`,
        `p-value at most: ${FILTER_HELP.pValue}`,
        `q-value at most: ${FILTER_HELP.qValue}`,
        `Correlation from / to: ${FILTER_HELP.correlation}`,
        `Effect from / to: ${FILTER_HELP.effect}`,
        `Only gene sets where its score passes: ${FILTER_HELP.modeOnly}`,
        `All gene sets holding it, passing ones first: ${FILTER_HELP.modeFirst}`,
      ]),
    );
  });

  it('says how many genes one search takes', () => {
    expect(FILTER_HELP.gene).toContain('Up to 5 genes');
  });
});
