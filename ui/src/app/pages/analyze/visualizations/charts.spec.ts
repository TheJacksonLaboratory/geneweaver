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

const titles = (host: HTMLElement) =>
  Array.from(host.querySelectorAll('title')).map((t) => t.textContent ?? '');

describe('HeatmapComponent', () => {
  it('a cell per ordered pair, shaded, with the p-value in the tooltip', () => {
    const model = jaccardMatrix(FIXTURES.jaccard_similarity_pair);
    const host = render(HeatmapComponent, { model });
    expect(host.querySelectorAll('svg g > g > rect')).toHaveLength(model.cells.length);
    expect(titles(host)).toContain('GS400405 vs GS14923: Jaccard 0.184, p 0.002, 9 shared');
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
});

describe('ClusterPackComponent', () => {
  it('a circle per cluster and per gene, each gene named in its tooltip', () => {
    const model = dbscanModel(FIXTURES.dbscan)!;
    const host = render(ClusterPackComponent, { model });
    const genes = FIXTURES.dbscan.clusters.flat();
    expect(host.querySelectorAll('svg circle')).toHaveLength(
      FIXTURES.dbscan.clusters.length + genes.length,
    );
    expect(titles(host)).toEqual(expect.arrayContaining(genes));
  });
});

describe('VennComponent', () => {
  const output = FIXTURES.boolean_algebra as unknown as BooleanAlgebraOutput;

  it('draws circles for two gene sets, sized by their genes', () => {
    const model = booleanModel({ ...output, geneset_ids: output.geneset_ids.slice(0, 2) });
    const host = render(VennComponent, { model });
    expect(host.querySelectorAll('svg circle')).toHaveLength(2);
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
    expect(host.querySelectorAll('svg rect')).toHaveLength(model.bins.length);
    expect(host.querySelector('svg line')).not.toBeNull();
    expect(host.textContent).toContain('observed 45 (p 0.000000)');
    expect(host.textContent).toContain('Universe Size');
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
