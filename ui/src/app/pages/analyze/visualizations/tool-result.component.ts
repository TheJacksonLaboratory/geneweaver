import { JsonPipe, NgIf, NgSwitch, NgSwitchCase, NgSwitchDefault } from '@angular/common';
import { ChangeDetectionStrategy, Component, Input, OnChanges } from '@angular/core';

import { AbbaResultComponent } from './abba-result.component';
import { ClusterPackComponent } from './cluster-pack.component';
import { CombineTableComponent } from './combine-table.component';
import { DendrogramComponent } from './dendrogram.component';
import { GeneNetworkComponent } from './gene-network.component';
import { HeatmapComponent } from './heatmap.component';
import {
  booleanModel,
  BooleanAlgebraOutput,
  BooleanModel,
  dbscanModel,
  dendrogramModel,
  DendrogramNode,
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
};

/**
 * Chooses and feeds the chart for one tool's result. The raw output stays available
 * underneath, both for checking a chart against its data and for anything a chart leaves
 * out.
 */
@Component({
  selector: 'app-tool-result',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    NgIf,
    NgSwitch,
    NgSwitchCase,
    NgSwitchDefault,
    JsonPipe,
    AbbaResultComponent,
    ClusterPackComponent,
    CombineTableComponent,
    DendrogramComponent,
    GeneNetworkComponent,
    HeatmapComponent,
    MsetEulerComponent,
    MsetHistogramComponent,
    PhenomeMapGraphComponent,
    SunburstComponent,
    UpsetPlotComponent,
    VennComponent,
    VennGridComponent,
    ViewSwitchComponent,
  ],
  template: `
    <app-view-switch
      *ngIf="views.length"
      [options]="views"
      [(value)]="view"
      label="Result view"
    ></app-view-switch>
    <ng-container [ngSwitch]="tool">
      <ng-container *ngSwitchCase="'upset'">
        <app-upset-plot *ngIf="upset" [model]="upset"></app-upset-plot>
      </ng-container>
      <ng-container *ngSwitchCase="'hypergeometric'">
        <p class="text-sm text-color-secondary mt-0">
          Over-representation of each pair's shared genes. Darker is more significant.
        </p>
        <app-heatmap *ngIf="matrix" [model]="matrix" filename="hypergeometric.svg"></app-heatmap>
      </ng-container>
      <ng-container *ngSwitchCase="'jaccard_similarity'">
        <ng-container *ngIf="view === 'venn'; else similarityMatrix">
          <p class="text-sm text-color-secondary mt-0">
            A Venn diagram per pair: row gene set against column gene set, with the Jaccard index
            (shared genes ÷ all genes) and p-value.
          </p>
          <app-venn-grid *ngIf="vennGrid" [model]="vennGrid"></app-venn-grid>
        </ng-container>
        <ng-template #similarityMatrix>
          <p class="text-sm text-color-secondary mt-0">
            Jaccard index (shared genes ÷ all genes) for each pair; p-values in the tooltips.
          </p>
          <app-heatmap *ngIf="matrix" [model]="matrix" filename="jaccard-similarity.svg"></app-heatmap>
        </ng-template>
      </ng-container>
      <ng-container *ngSwitchCase="'jaccard_clustering'">
        <ng-container *ngIf="tree; else empty">
          <app-dendrogram *ngIf="view === 'dendrogram'" [model]="tree" [method]="result['method']"></app-dendrogram>
          <app-sunburst *ngIf="view === 'sunburst'" [model]="tree" [method]="result['method']"></app-sunburst>
        </ng-container>
      </ng-container>
      <ng-container *ngSwitchCase="'dbscan'">
        <ng-container *ngIf="pack; else noClusters">
          <app-cluster-pack *ngIf="view === 'circles'" [model]="pack"></app-cluster-pack>
          <app-gene-network *ngIf="view === 'network'" [result]="$any(result)"></app-gene-network>
        </ng-container>
        <ng-template #noClusters>
          <p>
            DBSCAN did not cluster these genes{{ result['ran'] === false ? ': the parameters are too
            large for this many genes. Try a smaller epsilon or minimum points.' : '.' }}
          </p>
        </ng-template>
      </ng-container>
      <ng-container *ngSwitchCase="'boolean_algebra'">
        <app-venn *ngIf="boolean" [model]="boolean" [species]="species"></app-venn>
      </ng-container>
      <ng-container *ngSwitchCase="'mset'">
        <h4 class="mt-0">Size comparison</h4>
        <app-mset-euler
          *ngIf="euler"
          [model]="euler"
          [genes]="result['intersect_genes'] ?? []"
        ></app-mset-euler>
        <h4>Random overlaps</h4>
        <app-mset-histogram *ngIf="mset" [model]="mset"></app-mset-histogram>
      </ng-container>
      <ng-container *ngSwitchCase="'phenome_map'">
        <app-phenome-map-graph [result]="$any(result)"></app-phenome-map-graph>
      </ng-container>
      <ng-container *ngSwitchCase="'combine'">
        <app-combine-table [result]="$any(result)"></app-combine-table>
      </ng-container>
      <ng-container *ngSwitchCase="'abba'">
        <app-abba-result [result]="$any(result)"></app-abba-result>
      </ng-container>
      <p *ngSwitchDefault class="text-sm text-color-secondary">
        This tool has no visualisation yet; its result is below.
      </p>
    </ng-container>
    <ng-template #empty><p>Nothing to draw for this result.</p></ng-template>

    <details class="mt-3">
      <summary class="cursor-pointer text-sm">Raw result (JSON)</summary>
      <pre class="overflow-auto p-3 surface-100 border-round raw">{{ result | json }}</pre>
    </details>
  `,
  styles: ['.raw { max-height: 28rem; }'],
})
export class ToolResultComponent implements OnChanges {
  @Input({ required: true }) tool!: string;
  @Input({ required: true }) result!: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  @Input() geneCounts: Record<string, number> = {};

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

  ngOnChanges(): void {
    const r = this.result;
    this.views = VIEWS[this.tool] ?? [];
    this.view = this.views[0]?.id ?? '';
    this.upset = this.tool === 'upset'
      ? upsetModel(
          r['geneset_ids'] ?? [],
          this.geneCounts,
          (r['intersections'] ?? []).map((i: { genesets: string[]; size: number }) => ({
            geneset_ids: i.genesets,
            size: i.size,
          })),
        )
      : undefined;
    this.matrix =
      this.tool === 'hypergeometric'
        ? hypergeometricMatrix(r as Parameters<typeof hypergeometricMatrix>[0])
        : this.tool === 'jaccard_similarity'
          ? jaccardMatrix(r as Parameters<typeof jaccardMatrix>[0])
          : undefined;
    this.vennGrid =
      this.tool === 'jaccard_similarity'
        ? jaccardVennGrid(r as Parameters<typeof jaccardVennGrid>[0])
        : undefined;
    this.tree = this.tool === 'jaccard_clustering' ? dendrogramModel(r['tree']) : undefined;
    this.pack = this.tool === 'dbscan' ? dbscanModel(r as Parameters<typeof dbscanModel>[0]) : undefined;
    this.boolean =
      this.tool === 'boolean_algebra' ? booleanModel(r as BooleanAlgebraOutput) : undefined;
    this.species =
      this.tool === 'boolean_algebra' ? speciesSummary(r as BooleanAlgebraOutput) : null;
    this.mset = this.tool === 'mset' ? msetModel(r as Parameters<typeof msetModel>[0]) : undefined;
    this.euler = this.tool === 'mset' ? msetEuler(r as Parameters<typeof msetEuler>[0]) : undefined;
  }
}
