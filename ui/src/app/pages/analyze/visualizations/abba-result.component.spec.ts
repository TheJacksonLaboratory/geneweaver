import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { ABBA_FIXTURE } from './abba-fixture';
import { AbbaResult } from './abba-models';
import { AbbaResultComponent } from './abba-result.component';
import * as chartUtils from './chart-utils';

describe('AbbaResultComponent', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
  });

  function build(result: AbbaResult = ABBA_FIXTURE) {
    const fixture = TestBed.createComponent(AbbaResultComponent);
    fixture.componentInstance.result = result;
    fixture.componentInstance.ngOnChanges();
    fixture.detectChanges();
    return fixture;
  }

  const genesetIds = (host: HTMLElement) =>
    Array.from(host.querySelectorAll('table.genesets tbody td.title a')).map((a) => a.textContent!.match(/GS(\d+)/)![1]);

  it("shows legacy's four sections, each collapsible", () => {
    const host: HTMLElement = build().nativeElement;
    const titles = Array.from(host.querySelectorAll('details > summary')).map((s) => s.textContent!.trim());
    expect(titles).toEqual([
      'Run information',
      'Seed genes (19)',
      'Highly connected gene sets',
      'Genes of interest',
    ]);
    expect(Array.from(host.querySelectorAll('details')).every((d) => d.open)).toBe(true);
    expect(host.querySelector('.run-info')!.textContent).toContain('IN (1,2,3)');
  });

  it('colours each seed gene by its species, naming the species for screen readers', () => {
    const host: HTMLElement = build().nativeElement;
    const tiles = Array.from(host.querySelectorAll<HTMLElement>('.gene-tile'));
    expect(tiles).toHaveLength(19);
    const drd2 = tiles[0];
    expect(drd2.textContent).toContain('Drd2');
    expect(drd2.style.background).toMatch(/179, 205, 227|#b3cde3/i);
    expect(drd2.textContent).toContain('(Mus musculus)');
    expect(host.querySelectorAll('.species-tiles .tile')).toHaveLength(9);
  });

  it('shows a long seed list in part, with a way to see it all', () => {
    const seeds = Array.from({ length: 130 }, (_, i) => ({
      ode_gene_id: i,
      symbol: `G${i}`,
      species_id: 1,
      species: 'Mus musculus',
    }));
    const fixture = build({ ...ABBA_FIXTURE, seed_genes: seeds });
    const host: HTMLElement = fixture.nativeElement;
    expect(host.querySelectorAll('.gene-tile')).toHaveLength(120);
    const more = Array.from(host.querySelectorAll('button')).find((b) => b.textContent!.includes('Show all 130'))!;
    more.click();
    fixture.detectChanges();
    expect(host.querySelectorAll('.gene-tile')).toHaveLength(130);
  });

  it('lists the gene sets with tier, species, attribution and size badges, linked', () => {
    const host: HTMLElement = build().nativeElement;
    const first = host.querySelector('table.genesets tbody tr')!;
    const text = first.textContent!.replace(/\s+/g, ' ');
    expect(text).toContain('Tier I');
    expect(first.querySelector('[title="Tier I - Public Resource"]')).not.toBeNull();
    expect(text).toContain('Zebrafish');
    expect(text).toContain('KEGG');
    expect(text).toContain('358 genes');
    expect(text).toContain('4');
    expect(first.querySelector('a')!.getAttribute('href')).toBe('/geneset/282317');
  });

  it('sorts the gene sets when a sort is chosen -- legacy never wired its dropdown', () => {
    const fixture = build();
    const host: HTMLElement = fixture.nativeElement;
    expect(genesetIds(host)).toEqual(['282317', '282184', '259156', '265224', '169623', '321618', '241264']);
    const select = host.querySelector<HTMLSelectElement>('#abba-sort')!;
    select.value = 'species';
    select.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(genesetIds(host)).toEqual(['282317', '282184', '241264', '259156', '169623', '265224', '321618']);
  });

  it('ignores an empty sort event', () => {
    const fixture = build();
    fixture.componentInstance.sortBy('');
    expect(fixture.componentInstance.sortValue).toBe('none');
  });

  it('expands a gene set to its description, with aria-expanded kept in step', () => {
    const fixture = build();
    const host: HTMLElement = fixture.nativeElement;
    const expander = host.querySelector<HTMLButtonElement>('button.expander')!;
    expect(expander.getAttribute('aria-expanded')).toBe('false');
    expander.click();
    fixture.detectChanges();
    expect(expander.getAttribute('aria-expanded')).toBe('true');
    const description = host.querySelector('#abba-gs-282317')!;
    expect(description.textContent).toContain('Neuroactive ligand-receptor interaction');
  });

  it('hands the selected gene sets back, in table order', () => {
    const fixture = build();
    const host: HTMLElement = fixture.nativeElement;
    const emitted: number[][] = [];
    fixture.componentInstance.useGenesets.subscribe((ids) => emitted.push(ids));
    const boxes = host.querySelectorAll<HTMLInputElement>('table.genesets tbody input[type=checkbox]');
    boxes[2].click();
    boxes[0].click();
    fixture.detectChanges();
    const use = Array.from(host.querySelectorAll('button')).find((b) => b.textContent!.includes('Analyze form'))!;
    expect(use.textContent).toContain('Use 2 selected gene sets');
    use.click();
    expect(emitted).toEqual([[282317, 259156]]);
  });

  it('draws each gene row: symbols, species, an occurrence meter and two sparklines', () => {
    const host: HTMLElement = build().nativeElement;
    const rows = host.querySelectorAll('table.genes tbody tr');
    expect(rows).toHaveLength(6);
    const tnf = rows[0];
    expect(tnf.textContent).toContain('TNF');
    expect(tnf.textContent).toContain('TNF-alpha');
    expect(tnf.textContent).toContain('TNLG1F');
    expect(tnf.textContent).toContain('Human');
    const meter = tnf.querySelector('[role=meter]')!;
    expect(meter.getAttribute('aria-valuenow')).toBe('1453');
    expect(meter.getAttribute('aria-valuemax')).toBe('1453');
    expect(tnf.querySelector<HTMLElement>('.meter-fill')!.style.width).toBe('100%');
    const sparklines = tnf.querySelectorAll('app-abba-sparkline svg');
    expect(sparklines).toHaveLength(2);
    expect(sparklines[0].querySelectorAll('rect')).toHaveLength(5);
    expect(sparklines[1].querySelectorAll('rect')).toHaveLength(10);
  });

  it('gives a bar its own tooltip on hover, and the whole sparkline on focus', () => {
    const host: HTMLElement = build().nativeElement;
    const svg = host.querySelector('table.genes tbody tr app-abba-sparkline svg')!;
    svg.querySelectorAll('rect')[1].dispatchEvent(new MouseEvent('mouseenter'));
    const tooltip = svg.parentElement!.querySelector('.chart-tooltip')!;
    expect(tooltip.textContent).toBe('Tier II - Pro-curatedGene sets: ' + (4501).toLocaleString());

    svg.dispatchEvent(new FocusEvent('focus'));
    expect(tooltip.textContent).toContain('TNF: gene sets by curation tier');
    expect(tooltip.textContent).toContain('Tier V - Group/Private: 460');
    expect(svg.getAttribute('tabindex')).toBe('0');
    expect(svg.getAttribute('aria-label')).toContain('Tier I - Public Resource: ' + (2461).toLocaleString());
  });

  it('selects all genes, and shows a part selection as indeterminate', () => {
    const fixture = build();
    const host: HTMLElement = fixture.nativeElement;
    const all = host.querySelector<HTMLInputElement>('input.select-all')!;
    const rowBoxes = () =>
      Array.from(host.querySelectorAll<HTMLInputElement>('table.genes tbody input[type=checkbox]'));
    rowBoxes()[0].click();
    fixture.detectChanges();
    expect(all.indeterminate).toBe(true);
    all.click();
    fixture.detectChanges();
    expect(rowBoxes().every((box) => box.checked)).toBe(true);
    expect(all.checked).toBe(true);
    all.click();
    fixture.detectChanges();
    expect(rowBoxes().some((box) => box.checked)).toBe(false);
  });

  it('downloads the selected genes as CSV', () => {
    const save = jest.spyOn(chartUtils, 'saveBlob').mockImplementation(() => undefined);
    const fixture = build();
    const component = fixture.componentInstance;
    component.toggleGene(95197);
    component.downloadGenes();
    expect(save).toHaveBeenCalledWith(expect.any(Blob), 'abba-genes.csv');
    expect(component.status).toContain('Saved 1 gene');
    save.mockRestore();
  });

  it('copies the selected genes, one symbol per line', async () => {
    const writeText = jest.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const fixture = build();
    fixture.componentInstance.toggleAllGenes();
    fixture.componentInstance.copyGenes();
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledWith('TNF\nBDNF\nAPOE\nIL6\nMAPK1\nAKT1');
    expect(fixture.componentInstance.status).toBe('Copied 6 genes.');
  });

  it('says so when nothing matched', () => {
    const host: HTMLElement = build({ ...ABBA_FIXTURE, genesets: [], genes: [] }).nativeElement;
    expect(host.textContent).toContain('No gene set holds enough of the seed genes');
    expect(host.textContent).toContain('No gene recurs across the matching gene sets');
  });
});
