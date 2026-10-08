import { Type } from '@angular/core';
import { TestBed } from '@angular/core/testing';

import { ClusterPackComponent } from './cluster-pack.component';
import { CombineTableComponent } from './combine-table.component';
import { DendrogramComponent } from './dendrogram.component';
import { FIXTURES } from './fixtures';
import { HeatmapComponent } from './heatmap.component';
import {
  booleanModel,
  BooleanAlgebraOutput,
  dbscanModel,
  dendrogramModel,
  hypergeometricMatrix,
  jaccardMatrix,
  msetModel,
} from './models';
import { MsetHistogramComponent } from './mset-histogram.component';
import { ToolResultComponent } from './tool-result.component';
import { VennComponent } from './venn.component';

/** Create a chart component, give it inputs, and draw. */
function render<T extends object>(type: Type<T>, inputs: Partial<T>) {
  const fixture = TestBed.createComponent(type);
  Object.assign(fixture.componentInstance, inputs);
  (fixture.componentInstance as { ngOnChanges?: () => void }).ngOnChanges?.();
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

/** Hover a mark and return the tooltip's text. */
function hover(host: HTMLElement, mark: Element | null): string {
  if (!mark) {
    throw new Error('no mark to hover');
  }
  mark.dispatchEvent(new MouseEvent('mouseenter'));
  const tooltip = host.querySelector('.chart-tooltip') as HTMLElement;
  expect(tooltip.style.display).toBe('block');
  return tooltip.textContent ?? '';
}

function leave(host: HTMLElement, mark: Element): void {
  mark.dispatchEvent(new MouseEvent('mouseleave'));
  expect((host.querySelector('.chart-tooltip') as HTMLElement).style.display).toBe('none');
}

describe('chart accessibility', () => {
  it('is a labelled group, not an image, so its focusable marks stay exposed', () => {
    const host = render(HeatmapComponent, { model: jaccardMatrix(FIXTURES.jaccard_similarity_pair) });
    const svg = host.querySelector('svg')!;
    expect(svg.getAttribute('role')).toBe('group');
    expect(svg.getAttribute('aria-roledescription')).toBe('chart');
    const cells = Array.from(host.querySelectorAll('svg g > g > rect'));
    expect(cells.every((c) => c.getAttribute('tabindex') === '0' && c.getAttribute('aria-label'))).toBe(true);
  });
});

describe('HeatmapComponent', () => {
  it('a cell per ordered pair; hovering one gives the pair\'s statistics', () => {
    const model = jaccardMatrix(FIXTURES.jaccard_similarity_pair);
    const host = render(HeatmapComponent, { model });
    const cells = host.querySelectorAll('svg g > g > rect');
    expect(cells).toHaveLength(model.cells.length);
    const index = model.cells.findIndex((c) => c.row === '400405' && c.col === '14923');
    const text = hover(host, cells[index]);
    expect(text).toContain('GS400405 vs GS14923');
    expect(text).toContain('Jaccard index: 0.184');
    expect(text).toContain('p-value: 0.002');
    expect(text).toContain('Shared genes: 9');
    leave(host, cells[index]);
  });

  it('hovering a cell highlights its row and column', () => {
    const model = hypergeometricMatrix(FIXTURES.hypergeometric);
    const host = render(HeatmapComponent, { model });
    const cells = Array.from(host.querySelectorAll('svg g > g > rect'));
    const index = model.cells.findIndex((c) => c.row !== c.col);
    const target = model.cells[index];
    hover(host, cells[index]);
    const outside = model.cells.findIndex((c) => c.row !== target.row && c.col !== target.col);
    expect(cells[outside].getAttribute('opacity')).toBe('0.35');
    expect(cells[index].getAttribute('stroke')).toBe('#0F172A');
  });

  it('labels every gene set on both axes', () => {
    const model = hypergeometricMatrix(FIXTURES.hypergeometric);
    const text = render(HeatmapComponent, { model }).textContent ?? '';
    for (const id of model.ids) {
      expect(text.split(`GS${id}`).length - 1).toBeGreaterThanOrEqual(2);
    }
  });
});

describe('DendrogramComponent', () => {
  it('a leaf label per gene set and a dot per merge', () => {
    const model = dendrogramModel(FIXTURES.jaccard_clustering.tree)!;
    const host = render(DendrogramComponent, { model, method: 'average' });
    const text = host.textContent ?? '';
    for (const id of FIXTURES.jaccard_clustering.geneset_ids) {
      expect(text).toContain(`GS${id}`);
    }
    // n leaves are joined by n - 1 merges.
    expect(host.querySelectorAll('svg circle')).toHaveLength(
      FIXTURES.jaccard_clustering.geneset_ids.length - 1,
    );
    expect(host.querySelector('svg')?.getAttribute('aria-label')).toContain('average linkage');
  });

  it('hovering a merge names the gene sets it joins and highlights its subtree', () => {
    const model = dendrogramModel(FIXTURES.jaccard_clustering.tree)!;
    const host = render(DendrogramComponent, { model, method: 'average' });
    const root = host.querySelector('svg g circle');
    const text = hover(host, root);
    expect(text).toContain(`Cluster of ${FIXTURES.jaccard_clustering.geneset_ids.length} gene sets`);
    expect(text).toContain('Similarity');
    for (const id of FIXTURES.jaccard_clustering.geneset_ids) {
      expect(text).toContain(`GS${id}`);
    }
  });
});

describe('ClusterPackComponent', () => {
  it('a circle per cluster and per gene; hovering a gene names it and its cluster', () => {
    const model = dbscanModel(FIXTURES.dbscan)!;
    const host = render(ClusterPackComponent, { model });
    const genes = FIXTURES.dbscan.clusters.flat();
    expect(host.querySelectorAll('svg circle')).toHaveLength(
      FIXTURES.dbscan.clusters.length + genes.length,
    );
    const text = hover(host, host.querySelector('circle.gene'));
    expect(text).toContain(FIXTURES.dbscan.clusters[0][0]);
    expect(text).toContain('Cluster: Cluster 1');
  });

  it('clicking a cluster zooms into it, and the background zooms out', () => {
    const model = dbscanModel({ ran: true, clusters: [['A', 'B'], ['C', 'D', 'E']] })!;
    const host = render(ClusterPackComponent, { model });
    const view = host.querySelector('svg > g') as SVGGElement;
    const outline = host.querySelector('svg > g > g > circle') as SVGCircleElement;

    outline.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(view.getAttribute('data-focus')).toMatch(/^Cluster \d \(\d genes\)$/);

    host.querySelector('svg > rect')!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(view.getAttribute('data-focus')).toBeNull();
  });

  it('zooms from the keyboard: Enter on a cluster, Escape or the button to come back', () => {
    const model = dbscanModel({ ran: true, clusters: [['A', 'B'], ['C', 'D', 'E']] })!;
    const fixture = TestBed.createComponent(ClusterPackComponent);
    fixture.componentInstance.model = model;
    fixture.componentInstance.ngOnChanges();
    fixture.detectChanges();
    const host: HTMLElement = fixture.nativeElement;
    const view = host.querySelector('svg > g') as SVGGElement;
    const outline = host.querySelector('svg > g > g > circle') as SVGCircleElement;
    expect(outline.getAttribute('role')).toBe('button');

    outline.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    fixture.detectChanges();
    expect(view.getAttribute('data-focus')).not.toBeNull();
    const reset = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Show all clusters'),
    )!;
    expect(reset).toBeDefined();

    reset.click();
    fixture.detectChanges();
    expect(view.getAttribute('data-focus')).toBeNull();

    outline.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    expect(view.getAttribute('data-focus')).not.toBeNull();
    outline.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(view.getAttribute('data-focus')).toBeNull();
  });

  it('zooms without animating when the user prefers reduced motion', () => {
    const original = window.matchMedia;
    window.matchMedia = ((query: string) => ({ matches: query.includes('reduce') })) as typeof window.matchMedia;
    try {
      const model = dbscanModel({ ran: true, clusters: [['A', 'B'], ['C', 'D', 'E']] })!;
      const host = render(ClusterPackComponent, { model });
      const view = host.querySelector('svg > g') as SVGGElement;
      (host.querySelector('svg > g > g > circle') as SVGCircleElement).dispatchEvent(
        new MouseEvent('click', { bubbles: true }),
      );
      expect(view.getAttribute('transform')).toMatch(/scale\((?!1\))/);
    } finally {
      window.matchMedia = original;
    }
  });
});

describe('VennComponent', () => {
  const output = FIXTURES.boolean_algebra as unknown as BooleanAlgebraOutput;

  it('draws circles for two gene sets; hovering one gives its unique and shared genes', () => {
    const model = booleanModel({ ...output, geneset_ids: output.geneset_ids.slice(0, 2) });
    const host = render(VennComponent, { model });
    const circles = host.querySelectorAll('svg circle');
    expect(circles).toHaveLength(2);
    const text = hover(host, circles[0]);
    expect(text).toContain(`GS${model.sets[0].id}`);
    expect(text).toContain('Only in this set');
    expect(text).toContain(`Shared with GS${model.sets[1].id}`);
  });

  it('keeps the labels of identical sets apart', () => {
    // Two identical sets: both circles sit on the centroid, so "away from the group" has no
    // direction; the labels must still not land on the same point.
    const model = booleanModel({
      relation: 'Union',
      at_least: 2,
      geneset_ids: [1, 2],
      bool_results: { a: [[1, 'A', 1, 1], [1, 'A', 1, 2]], b: [[2, 'B', 1, 1], [2, 'B', 1, 2]] },
      circle_groups: { a: [1, 2], b: [1, 2] },
    });
    const host = render(VennComponent, { model });
    const labels = Array.from(host.querySelectorAll('svg g > g > text'));
    expect(labels).toHaveLength(2);
    expect(labels[0].getAttribute('x')).not.toBe(labels[1].getAttribute('x'));
  });

  it('warns when Except leaves out genes that are in only one set', () => {
    const model = booleanModel({
      relation: 'Except',
      at_least: 2,
      geneset_ids: [1, 2],
      bool_results: {
        dup: [[10, 'Ppp1ccb', 1, 1], [10, 'Mm.334198', 1, 1]],
        solo: [[11, 'Kit', 1, 2]],
      },
      circle_groups: { dup: [1, 1], solo: [2] },
      bool_except: { '1': { solo: [[11, 'Kit', 1, 2]] } },
    });
    const host = render(VennComponent, { model });
    expect(host.textContent).toContain('1 genes that are in only one gene set are missing');
  });

  it('falls back to the combination table for more than three gene sets', () => {
    const model = booleanModel(output);
    expect(model.sets.length).toBeGreaterThan(3);
    const host = render(VennComponent, { model });
    expect(host.querySelector('svg')).toBeNull();
    expect(host.textContent).toContain('Venn diagram is drawn for 2 or 3 gene sets');
    expect(host.textContent).toContain('Membership combinations');
  });

  it('warns when the intersection holds genes in too few distinct gene sets', () => {
    const model = booleanModel(output);
    const host = render(VennComponent, { model });
    expect(host.textContent).toContain(
      `${model.belowThreshold} of the ${model.result.length} genes in this intersection`,
    );
  });
});

describe('MsetHistogramComponent', () => {
  it('bars for the null distribution and a marked observed overlap', () => {
    const model = msetModel(FIXTURES.mset);
    const host = render(MsetHistogramComponent, { model });
    expect(host.querySelectorAll('svg rect[aria-label^="Overlap of"]')).toHaveLength(model.bins.length);
    expect(host.querySelector('svg line')).not.toBeNull();
    expect(host.textContent).toContain('observed 45 · p < 0.001');
    expect(host.textContent).toContain('Universe Size');
  });

  it('never labels a negative overlap on a small axis', () => {
    // The domain starts at -1 to keep the 0 bar off the axis; -1 must not be a tick label.
    const model = msetModel({
      intersect_genes: ['A'],
      mset_data: { 'List 1/2 Intersect': '3', 'P-Value': '0.2', 'Num Trials': '10' },
      mset_hist: { '0': '0.5', '1': '0.3', '2': '0.2' },
    });
    const host = render(MsetHistogramComponent, { model });
    const ticks = Array.from(host.querySelectorAll('svg .tick text')).map((t) => t.textContent ?? '');
    expect(ticks.length).toBeGreaterThan(0);
    expect(ticks.some((t) => /^[-−]/.test(t))).toBe(false);
    expect(ticks.every((t) => /^\d+$/.test(t.replace('%', '')))).toBe(true);
  });

  it('hovering a bar gives its share of trials; the marker gives the p-value', () => {
    const model = msetModel(FIXTURES.mset);
    const host = render(MsetHistogramComponent, { model });
    const bar = hover(host, host.querySelector('svg rect'));
    expect(bar).toContain('Overlap of 0 genes');
    expect(bar).toContain('Share of random trials: 91.1%');
    expect(bar).toContain('Trials: 911 of 1000');
    const rects = host.querySelectorAll('svg rect');
    const marker = hover(host, rects[rects.length - 1]);
    expect(marker).toContain('Observed overlap: 45 genes');
    expect(marker).toContain('p-value: < 0.001 (no sample as extreme)');
    expect(marker).toContain('Random trials at or above it: 0 of 1000');
  });
});

describe('CombineTableComponent', () => {
  it('a row per gene and a column per gene set', () => {
    const host = render(CombineTableComponent, { result: FIXTURES.combine });
    expect(host.querySelectorAll('tbody tr')).toHaveLength(
      Object.keys(FIXTURES.combine.matrix).length,
    );
    for (const id of FIXTURES.combine.geneset_ids) {
      expect(host.querySelector('thead')?.textContent).toContain(`GS${id}`);
    }
  });
});

describe('ToolResultComponent', () => {
  const cases: [string, Record<string, unknown>, string][] = [
    ['hypergeometric', FIXTURES.hypergeometric, 'app-heatmap'],
    ['jaccard_similarity', FIXTURES.jaccard_similarity, 'app-heatmap'],
    ['jaccard_clustering', FIXTURES.jaccard_clustering, 'app-dendrogram'],
    ['dbscan', FIXTURES.dbscan, 'app-cluster-pack'],
    ['boolean_algebra', FIXTURES.boolean_algebra, 'app-venn'],
    ['mset', FIXTURES.mset, 'app-mset-histogram'],
    ['combine', FIXTURES.combine, 'app-combine-table'],
  ];

  it.each(cases)('%s gets its chart, with the raw result kept underneath', (tool, result, selector) => {
    const host = render(ToolResultComponent, { tool, result });
    expect(host.querySelector(selector)).not.toBeNull();
    expect(host.querySelector('details summary')?.textContent).toContain('Raw result');
  });

  it('upset, through the generic endpoint, maps its intersections for the plot', () => {
    const generic = {
      geneset_ids: ['1', '2'],
      include_homology: false,
      intersections: [{ genesets: ['1', '2'], size: 3 }, { genesets: ['1'], size: 2 }],
    };
    const host = render(ToolResultComponent, {
      tool: 'upset',
      result: generic,
      geneCounts: { '1': 5, '2': 3 },
    });
    expect(host.querySelector('app-upset-plot svg')).not.toBeNull();
  });

  it('a DBSCAN run that declined explains why instead of drawing nothing', () => {
    const host = render(ToolResultComponent, {
      tool: 'dbscan',
      result: { ran: false, clusters: [], num_genes: 3, num_genesets: 2 },
    });
    expect(host.textContent).toContain('parameters are too');
  });

  it('an unknown tool shows its raw result', () => {
    const host = render(ToolResultComponent, { tool: 'abba', result: { x: 1 } });
    expect(host.textContent).toContain('no visualisation yet');
    expect(host.querySelector('pre')?.textContent).toContain('"x": 1');
  });
});
