import { JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnChanges, input } from '@angular/core';

import { AbbaResultComponent } from './abba-result.component';
import { ClusterPackComponent } from './cluster-pack.component';
import { CombineTableComponent } from './combine-table.component';
import { DendrogramComponent } from './dendrogram.component';
import { GeneNetworkComponent } from './gene-network.component';
import { GenesetGraphComponent } from './geneset-graph.component';
import { HeatmapComponent } from './heatmap.component';
import {
  booleanModel,
  BooleanAlgebraOutput,
  BooleanModel,
  dbscanModel,
  dendrogramModel,
  DendrogramNode,
  genesetLabel,
  hypergeometricMatrix,
  jaccardMatrix,
  jaccardVennGrid,
  MatrixModel,
  msetEuler,
  MsetEuler,
  msetModel,
  MsetModel,
  PackNode,
  speciesSummary,
  SpeciesSummaryRow,
  upsetModel,
  UpSetModel,
  VennGridModel,
} from './models';
import { MsetEulerComponent } from './mset-euler.component';
import { MsetHistogramComponent } from './mset-histogram.component';
import { PhenomeMapGraphComponent } from './phenome-map-graph.component';
import { SunburstComponent } from './sunburst.component';
import { TricliqueComponent } from './triclique.component';
import { UpsetPlotComponent } from './upset-plot.component';
import { VennGridComponent } from './venn-grid.component';
import { VennComponent } from './venn.component';
import { ViewSwitchComponent } from './view-switch.component';

/** The views each tool offers, first the default; legacy's set for each tool. */
const VIEWS: Record<string, { id: string; label: string }[]> = {
  jaccard_similarity: [
    { id: 'venn', label: 'Venn grid' },
    { id: 'matrix', label: 'Similarity matrix' },
  ],
  jaccard_clustering: [
    { id: 'dendrogram', label: 'Dendrogram' },
    { id: 'sunburst', label: 'Sunburst' },
  ],
  dbscan: [
    { id: 'circles', label: 'Circles' },
    { id: 'network', label: 'Network' },
  ],
  geneset_graph: [
    { id: 'graph', label: 'Graph' },
    { id: 'table', label: 'Genes by degree' },
  ],
  triclique: [
    { id: 'edge', label: 'Most links' },
    { id: 'vertex', label: 'Most members' },
  ],
};

/**
 * Chooses and feeds the chart for one tool's result. The raw output stays available
 * underneath, both for checking a chart against its data and for anything a chart leaves
 * out.
 */
@Component({
  selector: 'app-tool-result',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    JsonPipe,
    AbbaResultComponent,
    ClusterPackComponent,
    CombineTableComponent,
    DendrogramComponent,
    GeneNetworkComponent,
    GenesetGraphComponent,
    HeatmapComponent,
    MsetEulerComponent,
    MsetHistogramComponent,
    PhenomeMapGraphComponent,
    SunburstComponent,
    TricliqueComponent,
    UpsetPlotComponent,
    VennComponent,
    VennGridComponent,
    ViewSwitchComponent
],
  template: `
    @if (views.length) {
      <app-view-switch
        [options]="views"
        [(value)]="view"
        label="Result view"
      ></app-view-switch>
    }
    @switch (tool()) {
      @case ('upset') {
        @if (upset) {
          <app-upset-plot [model]="upset"></app-upset-plot>
        }
      }
      @case ('hypergeometric') {
        <p class="text-sm text-color-secondary mt-0">
          Over-representation of each pair's shared genes. Darker is more significant.
        </p>
        @if (matrix) {
          <app-heatmap [model]="matrix" filename="hypergeometric.svg"></app-heatmap>
        }
      }
      @case ('jaccard_similarity') {
        @if (view === 'venn') {
          <p class="text-sm text-color-secondary mt-0">
            A Venn diagram per pair: row gene set against column gene set, with the Jaccard index
            (shared genes ÷ all genes) and p-value.
          </p>
          @if (vennGrid) {
            <app-venn-grid [model]="vennGrid"></app-venn-grid>
          }
        } @else {
          <p class="text-sm text-color-secondary mt-0">
            Jaccard index (shared genes ÷ all genes) for each pair; p-values in the tooltips.
          </p>
          @if (matrix) {
            <app-heatmap [model]="matrix" filename="jaccard-similarity.svg"></app-heatmap>
          }
        }
      }
      @case ('jaccard_clustering') {
        @if (tree) {
          @if (view === 'dendrogram') {
            <app-dendrogram [model]="tree" [method]="result()['method']"></app-dendrogram>
          }
          @if (view === 'sunburst') {
            <app-sunburst [model]="tree" [method]="result()['method']"></app-sunburst>
          }
        } @else {
          <p>Nothing to draw for this result.</p>
        }
      }
      @case ('geneset_graph') {
        @if (view === 'graph') {
          <app-geneset-graph [result]="$any(result())"></app-geneset-graph>
        }
        @if (view === 'table') {
          <table class="degree-table text-sm w-full">
            <caption class="text-left text-color-secondary mb-2">
              Genes held by at least {{ result()['min_degree'] }} of the gene sets, most shared first.
            </caption>
            <thead>
              <tr><th scope="col">Gene</th><th scope="col">Gene sets</th><th scope="col">Which</th></tr>
            </thead>
            <tbody>
              @for (gene of $any(result())['genes']; track gene) {
                <tr>
                  <td>{{ gene.symbol }}@if (gene.emphasized) {
                    <span class="ml-1" title="Emphasised">★</span>
                  }</td>
                  <td>{{ gene.degree }}</td>
                  <td>{{ genesetList(gene.genesets) }}</td>
                </tr>
              }
              @if (!$any(result())['genes']?.length) {
                <tr>
                  <td colspan="3">No gene is in that many of these gene sets.</td>
                </tr>
              }
            </tbody>
          </table>
        }
      }
      @case ('triclique') {
        <app-triclique [result]="$any(result())" [maximum]="$any(view)"></app-triclique>
      }
      @case ('dbscan') {
        @if (pack) {
          @if (view === 'circles') {
            <app-cluster-pack [model]="pack"></app-cluster-pack>
          }
          @if (view === 'network') {
            <app-gene-network [result]="$any(result())"></app-gene-network>
          }
        } @else {
          <p>
            DBSCAN did not cluster these genes{{ result()['ran'] === false ? ': the parameters are too
            large for this many genes. Try a smaller epsilon or minimum points.' : '.' }}
          </p>
        }
      }
      @case ('boolean_algebra') {
        @if (boolean) {
          <app-venn [model]="boolean" [species]="species"></app-venn>
        }
      }
      @case ('mset') {
        <h4 class="mt-0">Size comparison</h4>
        @if (euler) {
          <app-mset-euler
            [model]="euler"
            [genes]="result()['intersect_genes'] ?? []"
          ></app-mset-euler>
        }
        <h4>Random overlaps</h4>
        @if (mset) {
          <app-mset-histogram [model]="mset"></app-mset-histogram>
        }
      }
      @case ('phenome_map') {
        <app-phenome-map-graph [result]="$any(result())"></app-phenome-map-graph>
      }
      @case ('combine') {
        <app-combine-table [result]="$any(result())"></app-combine-table>
      }
      @case ('abba') {
        <app-abba-result [result]="$any(result())"></app-abba-result>
      }
      @default {
        <p class="text-sm text-color-secondary">
          This tool has no visualisation yet; its result is below.
        </p>
      }
    }
    
    <details class="mt-3">
      <summary class="cursor-pointer text-sm">Raw result (JSON)</summary>
      <pre class="overflow-auto p-3 surface-100 border-round raw">{{ result() | json }}</pre>
    </details>
    `,
  styles: ['.raw { max-height: 28rem; }'],
})
export class ToolResultComponent implements OnChanges {
  readonly tool = input.required<string>();
  readonly result = input.required<Record<string, any>>(); // eslint-disable-line @typescript-eslint/no-explicit-any
  readonly geneCounts = input<Record<string, number>>({});

  upset?: UpSetModel;
  matrix?: MatrixModel;
  vennGrid?: VennGridModel;
  tree?: DendrogramNode | null;
  pack?: PackNode | null;
  boolean?: BooleanModel;
  species: SpeciesSummaryRow[] | null = null;
  mset?: MsetModel;
  euler?: MsetEuler | null;
  views: { id: string; label: string }[] = [];
  view = '';

  /** "GS1, GS2", for the gene table. */
  genesetList(ids: string[]): string {
    return ids.map(genesetLabel).join(', ');
  }

  ngOnChanges(): void {
    const r = this.result();
    this.views = VIEWS[this.tool()] ?? [];
    this.view = this.views[0]?.id ?? '';
    this.upset = this.tool() === 'upset'
      ? upsetModel(
          r['geneset_ids'] ?? [],
          this.geneCounts(),
          (r['intersections'] ?? []).map((i: { genesets: string[]; size: number }) => ({
            geneset_ids: i.genesets,
            size: i.size,
          })),
        )
      : undefined;
    const tool = this.tool();
    this.matrix =
      tool === 'hypergeometric'
        ? hypergeometricMatrix(r as Parameters<typeof hypergeometricMatrix>[0])
        : tool === 'jaccard_similarity'
          ? jaccardMatrix(r as Parameters<typeof jaccardMatrix>[0])
          : undefined;
    this.vennGrid =
      this.tool() === 'jaccard_similarity'
        ? jaccardVennGrid(r as Parameters<typeof jaccardVennGrid>[0], this.geneCounts())
        : undefined;
    this.tree = this.tool() === 'jaccard_clustering' ? dendrogramModel(r['tree']) : undefined;
    this.pack = this.tool() === 'dbscan' ? dbscanModel(r as Parameters<typeof dbscanModel>[0]) : undefined;
    this.boolean =
      this.tool() === 'boolean_algebra' ? booleanModel(r as BooleanAlgebraOutput) : undefined;
    this.species =
      this.tool() === 'boolean_algebra' ? speciesSummary(r as BooleanAlgebraOutput) : null;
    this.mset = this.tool() === 'mset' ? msetModel(r as Parameters<typeof msetModel>[0]) : undefined;
    this.euler = this.tool() === 'mset' ? msetEuler(r as Parameters<typeof msetEuler>[0]) : undefined;
  }
}
