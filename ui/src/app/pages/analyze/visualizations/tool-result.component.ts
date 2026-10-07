import { JsonPipe, NgIf, NgSwitch, NgSwitchCase, NgSwitchDefault } from '@angular/common';
import { ChangeDetectionStrategy, Component, Input, OnChanges } from '@angular/core';

import { ClusterPackComponent } from './cluster-pack.component';
import { CombineTableComponent } from './combine-table.component';
import { DendrogramComponent } from './dendrogram.component';
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
  MatrixModel,
  msetModel,
  MsetModel,
  PackNode,
  upsetModel,
  UpSetModel,
} from './models';
import { MsetHistogramComponent } from './mset-histogram.component';
import { PhenomeMapGraphComponent } from './phenome-map-graph.component';
import { UpsetPlotComponent } from './upset-plot.component';
import { VennComponent } from './venn.component';

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
    ClusterPackComponent,
    CombineTableComponent,
    DendrogramComponent,
    HeatmapComponent,
    MsetHistogramComponent,
    PhenomeMapGraphComponent,
    UpsetPlotComponent,
    VennComponent,
  ],
  template: `
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
        <p class="text-sm text-color-secondary mt-0">
          Jaccard index (shared genes ÷ all genes) for each pair; p-values in the tooltips.
        </p>
        <app-heatmap *ngIf="matrix" [model]="matrix" filename="jaccard-similarity.svg"></app-heatmap>
      </ng-container>
      <ng-container *ngSwitchCase="'jaccard_clustering'">
        <app-dendrogram *ngIf="tree; else empty" [model]="tree" [method]="result['method']"></app-dendrogram>
      </ng-container>
      <ng-container *ngSwitchCase="'dbscan'">
        <app-cluster-pack *ngIf="pack; else noClusters" [model]="pack"></app-cluster-pack>
        <ng-template #noClusters>
          <p>
            DBSCAN did not cluster these genes{{ result['ran'] === false ? ': the parameters are too
            large for this many genes. Try a smaller epsilon or minimum points.' : '.' }}
          </p>
        </ng-template>
      </ng-container>
      <ng-container *ngSwitchCase="'boolean_algebra'">
        <app-venn *ngIf="boolean" [model]="boolean"></app-venn>
      </ng-container>
      <ng-container *ngSwitchCase="'mset'">
        <app-mset-histogram *ngIf="mset" [model]="mset"></app-mset-histogram>
      </ng-container>
      <ng-container *ngSwitchCase="'phenome_map'">
        <app-phenome-map-graph [result]="$any(result)"></app-phenome-map-graph>
      </ng-container>
      <ng-container *ngSwitchCase="'combine'">
        <app-combine-table [result]="$any(result)"></app-combine-table>
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
  tree?: DendrogramNode | null;
  pack?: PackNode | null;
  boolean?: BooleanModel;
  mset?: MsetModel;

  ngOnChanges(): void {
    const r = this.result;
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
    this.tree = this.tool === 'jaccard_clustering' ? dendrogramModel(r['tree']) : undefined;
    this.pack = this.tool === 'dbscan' ? dbscanModel(r as Parameters<typeof dbscanModel>[0]) : undefined;
    this.boolean =
      this.tool === 'boolean_algebra' ? booleanModel(r as BooleanAlgebraOutput) : undefined;
    this.mset = this.tool === 'mset' ? msetModel(r as Parameters<typeof msetModel>[0]) : undefined;
  }
}
