import { TestBed } from '@angular/core/testing';

import { FIXTURES } from './fixtures';
import { PhenomeMapGraphComponent } from './phenome-map-graph.component';

/**
 * Cytoscape renders to canvas, which the test DOM does not have, so the module is mocked:
 * these tests check what the component hands Cytoscape and how it reacts to a click, not
 * Cytoscape's drawing.
 */
const created: { options: Record<string, any>; handlers: Record<string, (e: unknown) => void> }[] = [];
/** A stand-in element that records its classes, for the search highlight. */
function element(id: string, source?: string, target?: string) {
  const classes = new Set<string>();
  return {
    classes,
    id: () => id,
    source: () => ({ id: () => source }),
    target: () => ({ id: () => target }),
    addClass: (name: string) => classes.add(name),
    removeClass: (names: string) => names.split(' ').forEach((name) => classes.delete(name)),
  };
}

jest.mock('cytoscape', () => ({
  __esModule: true,
  default: (options: Record<string, any>) => {
    const elements = (options['elements'] as { group: string; data: Record<string, string> }[]).map(
      (e) => ({ group: e.group, el: element(e.data['id'], e.data['source'], e.data['target']) }),
    );
    const collection = (group?: string) => {
      const items = elements.filter((e) => !group || e.group === group).map((e) => e.el);
      return {
        forEach: (fn: (el: (typeof items)[number]) => void) => items.forEach(fn),
        removeClass: (names: string) => items.forEach((el) => el.removeClass(names)),
      };
    };
    const instance = {
      options,
      classesOf: (id: string) => elements.find((e) => e.el.id() === id)?.el.classes,
      batch: (fn: () => void) => fn(),
      elements: () => collection(),
      nodes: () => collection('nodes'),
      edges: () => collection('edges'),
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

  it('shows legacy\'s stats for the run', async () => {
    const fixture = await build();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Bicliques shown:');
    expect(text).toContain('448');
  });

  it('highlights the bicliques holding a searched gene, and fades the rest', async () => {
    const fixture = await build();
    const nodes = FIXTURES.phenome_map.nodes;
    // A gene some bicliques lack: the top biclique's genes are in every one of them.
    const gene = nodes.flatMap((n) => n.genes).find((g) => nodes.some((n) => !n.genes.includes(g)))!;
    const top = nodes.find((n) => n.genes.includes(gene))!;
    const input: HTMLInputElement = fixture.nativeElement.querySelector('#phenome-map-search');
    input.value = gene.toLowerCase();
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const cy = created[0] as any;
    const holding = nodes.filter((n) => n.genes.includes(gene));
    expect(fixture.nativeElement.textContent).toContain(`${holding.length} of 26 bicliques contain a match`);
    expect(cy.classesOf(`n${top.id}`).has('matched')).toBe(true);
    const other = nodes.find((n) => !n.genes.includes(gene) && n.displayed !== false)!;
    expect(cy.classesOf(`n${other.id}`).has('dimmed')).toBe(true);

    // Clearing the search clears the highlight.
    input.value = '';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(cy.classesOf(`n${other.id}`).size).toBe(0);
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
