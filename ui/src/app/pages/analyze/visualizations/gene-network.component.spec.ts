import { TestBed } from '@angular/core/testing';

import { FIXTURES } from './fixtures';
import { GeneNetworkComponent } from './gene-network.component';

/** Cytoscape draws to canvas, which the test DOM lacks: check what it is handed instead. */
const created: { options: Record<string, any>; handlers: Record<string, (e: unknown) => void> }[] = [];
jest.mock('cytoscape', () => ({
  __esModule: true,
  default: (options: Record<string, unknown>) => {
    const instance = {
      options,
      handlers: {} as Record<string, (e: unknown) => void>,
      on(event: string, _selector: string, handler: (e: unknown) => void) {
        this.handlers[event] = handler;
      },
      destroy: jest.fn(),
      selected: [] as string[],
      $: jest.fn(() => ({ unselect: jest.fn() })),
      getElementById(id: string) {
        return { select: () => this.selected.push(id) };
      },
    };
    created.push(instance);
    return instance;
  },
}));

describe('GeneNetworkComponent', () => {
  beforeEach(() => (created.length = 0));

  async function build(result: Record<string, unknown> = FIXTURES.dbscan) {
    const fixture = TestBed.createComponent(GeneNetworkComponent);
    fixture.componentInstance.result = result as GeneNetworkComponent['result'];
    await fixture.componentInstance.ngOnChanges();
    fixture.detectChanges();
    return fixture;
  }

  it('hands Cytoscape a node per gene, coloured by cluster, and a link per shared gene set', async () => {
    const fixture = await build();
    const elements = created[0].options['elements'] as { group: string; data: Record<string, unknown> }[];
    expect(elements.filter((e) => e.group === 'nodes')).toHaveLength(12);
    expect(elements.filter((e) => e.group === 'edges')).toHaveLength(66);
    expect(fixture.nativeElement.textContent).toContain('Cluster 1');
    expect(fixture.nativeElement.querySelector('[role="img"]').getAttribute('aria-label')).toBe(
      'Network of 12 genes and 66 links',
    );
  });

  it('grey noise genes get their own legend entry', async () => {
    const fixture = await build({
      ran: true,
      clusters: [['A', 'B']],
      gene_genesets: { A: ['1'], B: ['1'], C: ['1'] },
    });
    expect(fixture.nativeElement.textContent).toContain('Noise (no cluster)');
  });

  it('a gene chosen from the list, or tapped, shows its cluster and gene sets', async () => {
    const fixture = await build();
    const select: HTMLSelectElement = fixture.nativeElement.querySelector('#network-gene-picker');
    select.value = 'Cnr1';
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Cluster: 1');
    expect(text).toContain('GS167180, GS378899, GS164706');
    expect((created[0] as any).selected).toContain('Cnr1');

    created[0].handlers['tap']({ target: { id: () => 'Hltf' } });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Gene sets: GS167180');
  });

  it('creates nothing if destroyed while Cytoscape is still loading', async () => {
    const fixture = TestBed.createComponent(GeneNetworkComponent);
    fixture.componentInstance.result = FIXTURES.dbscan;
    const pending = fixture.componentInstance.ngOnChanges();
    fixture.destroy();
    await pending;
    expect(created).toHaveLength(0);
  });
});
