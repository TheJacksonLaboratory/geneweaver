import { TestBed } from '@angular/core/testing';

import { FIXTURES } from './fixtures';
import { PhenomeMapGraphComponent } from './phenome-map-graph.component';

/**
 * Cytoscape renders to canvas, which the test DOM does not have, so the module is mocked:
 * these tests check what the component hands Cytoscape and how it reacts to a click, not
 * Cytoscape's drawing.
 */
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
      fit: jest.fn(),
      png: jest.fn(() => new Blob()),
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

describe('PhenomeMapGraphComponent', () => {
  beforeEach(() => (created.length = 0));

  async function build() {
    const fixture = TestBed.createComponent(PhenomeMapGraphComponent);
    fixture.componentInstance.result = FIXTURES.phenome_map;
    await fixture.componentInstance.ngOnChanges();
    fixture.detectChanges();
    return fixture;
  }

  it('hands Cytoscape every displayed biclique, positioned in the tool\'s own levels', async () => {
    const fixture = await build();
    const { options } = created[0];
    const nodes = options['elements'].filter((e: { group: string }) => e.group === 'nodes');
    expect(nodes).toHaveLength(26);
    // Preset positions from the tool's depths; an inferred layout drew links sideways.
    expect(options['layout'].name).toBe('preset');
    expect(nodes.every((n: { position?: unknown }) => n.position)).toBe(true);
    expect(options['container']).toBe(fixture.componentInstance.graph.nativeElement);
    expect(fixture.nativeElement.querySelector('[role="img"]').getAttribute('aria-label')).toBe(
      'PhenomeMap graph of 26 bicliques',
    );
  });

  it('lists a clicked biclique\'s gene sets and genes', async () => {
    const fixture = await build();
    const node = FIXTURES.phenome_map.nodes[0];
    created[0].handlers['tap']({ target: { id: () => `n${node.id}` } });
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain(`Gene sets (${node.genesets.length})`);
    expect(text).toContain(node.genes.join(', '));
  });

  it('replaces, not stacks, the graph when the result changes, and cleans up', async () => {
    const fixture = await build();
    await fixture.componentInstance.ngOnChanges();
    expect(created).toHaveLength(2);
    expect((created[0] as any).destroy).toHaveBeenCalled();
    fixture.destroy();
    expect((created[1] as any).destroy).toHaveBeenCalled();
  });

  it('a biclique can be chosen from a native list, the keyboard way in', async () => {
    const fixture = await build();
    const select: HTMLSelectElement = fixture.nativeElement.querySelector('#biclique-picker');
    // One option per displayed biclique, plus the prompt; top level first.
    expect(select.options).toHaveLength(26 + 1);
    expect(select.options[1].textContent).toMatch(/^Level 0: /);

    const node = FIXTURES.phenome_map.nodes[3];
    select.value = `n${node.id}`;
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain(node.genes.join(', '));
    // ...and the graph shows the same node selected.
    expect((created[0] as any).selected).toContain(`n${node.id}`);
  });

  it('a click on the graph updates the list, so both stay in step', async () => {
    const fixture = await build();
    const node = FIXTURES.phenome_map.nodes[2];
    created[0].handlers['tap']({ target: { id: () => `n${node.id}` } });
    fixture.detectChanges();
    expect(fixture.componentInstance.selectedId).toBe(`n${node.id}`);
  });

  it('creates nothing if destroyed while Cytoscape is still loading', async () => {
    const fixture = TestBed.createComponent(PhenomeMapGraphComponent);
    fixture.componentInstance.result = FIXTURES.phenome_map;
    const pending = fixture.componentInstance.ngOnChanges();
    fixture.destroy();
    await pending;
    expect(created).toHaveLength(0);
  });

  it('a newer result supersedes a slower, older one', async () => {
    const fixture = TestBed.createComponent(PhenomeMapGraphComponent);
    fixture.componentInstance.result = FIXTURES.phenome_map;
    const older = fixture.componentInstance.ngOnChanges();
    const newer = fixture.componentInstance.ngOnChanges();
    await Promise.all([older, newer]);
    expect(created).toHaveLength(1);
  });
});
