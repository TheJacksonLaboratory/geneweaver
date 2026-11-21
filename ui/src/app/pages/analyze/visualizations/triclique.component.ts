
import { ChangeDetectionStrategy, Component, ElementRef, Input, OnChanges, ViewChild } from '@angular/core';

import { downloadSvg } from './chart-utils';
import { genesetLabel, Triclique, TricliqueModel, tricliqueModel, TricliqueOutput } from './models';

/**
 * Triclique (legacy TricliqueViewer): the largest clique across two groups of gene sets and
 * the genes they share, drawn as a triangle. Legacy's result was the edge maximum (the most
 * links); the vertex maximum (the most gene sets and genes) is the other view, as the search
 * keeps both. Plain SVG: a clique is small, and every link is implied by its members.
 */
@Component({
  selector: 'app-triclique',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [],
  template: `
    <p class="text-sm text-color-secondary mt-0">
      Group A: {{ list(result.group_a) }}. Group B: {{ list(result.group_b) }}.
      {{ result.shared_genes.length }} gene{{ result.shared_genes.length === 1 ? '' : 's' }} in both
      groups; {{ result.maximal_tricliques }} maximal triclique{{ result.maximal_tricliques === 1 ? '' : 's' }}.
    </p>
    @if (model) {
      <p class="text-sm mt-0">{{ model.summary }}</p>
      <div #chart class="overflow-auto">
        <svg
          [attr.width]="model.width"
          [attr.height]="model.height"
          [attr.viewBox]="'0 0 ' + model.width + ' ' + model.height"
          role="img"
          [attr.aria-label]="'Triclique: ' + model.summary"
          style="font: 11px sans-serif"
          >
          <g stroke="#94A3B8" stroke-opacity="0.45">
            @for (link of model.links; track link) {
              <line
                [attr.x1]="link.source.x"
                [attr.y1]="link.source.y"
                [attr.x2]="link.target.x"
                [attr.y2]="link.target.y"
              ></line>
            }
          </g>
          @for (node of model.nodes; track node) {
            <g [attr.transform]="'translate(' + node.x + ',' + node.y + ')'">
              <title>{{ node.label }}</title>
              @if (node.part !== 'gene') {
                <rect
                  x="-7"
                  y="-7"
                  width="14"
                  height="14"
                  rx="3"
                  [attr.fill]="node.part === 'a' ? '#4E79A7' : '#F28E2B'"
                ></rect>
              }
              @if (node.part === 'gene') {
                <circle r="5" fill="#59A14F"></circle>
              }
              @if (node.part === 'a') {
                <text
                  x="-12"
                  dy="0.35em"
                  text-anchor="end"
                >{{ node.label }}</text>
              }
              @if (node.part === 'b') {
                <text x="12" dy="0.35em">{{ node.label }}</text>
              }
              @if (node.part === 'gene') {
                <text transform="rotate(45)" x="9" dy="0.35em">{{ node.label }}</text>
              }
            </g>
          }
        </svg>
      </div>
      <ul class="list-none p-0 m-0 mt-2 flex flex-wrap gap-3 text-sm">
        <li><span class="swatch" style="background: #4E79A7"></span>Group A</li>
        <li><span class="swatch" style="background: #F28E2B"></span>Group B</li>
        <li><span class="swatch round" style="background: #59A14F"></span>Shared gene</li>
      </ul>
      <button type="button" class="p-button p-button-sm p-button-text mt-2" (click)="download()">
        Download SVG
      </button>
    } @else {
      <p>
        No triclique: no gene is in a gene set of each group whose two gene sets also share a gene.
      </p>
    }
    `,
  styles: [
    '.swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; }',
    '.swatch.round { border-radius: 50%; }',
  ],
})
export class TricliqueComponent implements OnChanges {
  @Input({ required: true }) result!: TricliqueOutput;
  /** Which kept clique to draw. */
  @Input() maximum: 'edge' | 'vertex' = 'edge';
  @ViewChild('chart') chart?: ElementRef<HTMLElement>;

  model?: TricliqueModel;

  ngOnChanges(): void {
    const clique: Triclique | null =
      this.maximum === 'edge' ? this.result.edge_maximum : this.result.vertex_maximum;
    this.model = clique ? tricliqueModel(clique) : undefined;
  }

  list(ids: string[]): string {
    return ids.map(genesetLabel).join(', ');
  }

  download(): void {
    if (this.chart) {
      downloadSvg(this.chart.nativeElement, `triclique-${this.maximum}-maximum.svg`);
    }
  }
}
