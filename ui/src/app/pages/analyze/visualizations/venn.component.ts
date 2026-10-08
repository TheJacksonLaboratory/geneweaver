import { NgFor, NgIf } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
} from '@angular/core';
import { schemeTableau10 } from 'd3';
import { TableModule } from 'primeng/table';

import { ChartTooltip, downloadSvg, freshSvg, interactive } from './chart-utils';
import { BooleanModel, genesetLabel, vennLayout } from './models';

/**
 * BooleanAlgebra: an area-proportional Venn diagram for two or three gene sets (more
 * cannot be drawn faithfully with circles), the exact membership combinations as a table
 * for any number, and the relation's answer as a gene list.
 */
@Component({
  selector: 'app-venn',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIf, NgFor, TableModule],
  template: `
    <div *ngIf="model.missingFromExcept" class="p-3 mb-3 border-round surface-100 text-sm warn">
      {{ model.missingFromExcept }} genes that are in only one gene set are missing from this
      result. The tool counts a gene once per identifier (symbol and UniGene id, say), so a gene
      listed twice in one set looks like it is in two, and is left out (G3-830).
    </div>
    <div *ngIf="model.belowThreshold" class="p-3 mb-3 border-round surface-100 text-sm warn">
      {{ model.belowThreshold }} of the {{ model.result.length }} genes in this
      {{ model.relation.toLowerCase() }} are in fewer than {{ model.atLeast }} distinct gene sets.
      The tool counts a gene once per identifier (symbol and UniGene id, say), so a gene listed
      twice in one set passes. Read the gene sets column, not the count.
    </div>

    <div #chart [hidden]="!drawn"></div>
    <p *ngIf="!drawn" class="text-sm text-color-secondary">
      A Venn diagram is drawn for 2 or 3 gene sets; the combinations below cover any number.
    </p>
    <button *ngIf="drawn" type="button" class="p-button p-button-sm p-button-text" (click)="download()">
      Download SVG
    </button>

    <h4>Membership combinations</h4>
    <p-table [value]="model.combinations" styleClass="p-datatable-sm" [scrollable]="true" scrollHeight="240px">
      <ng-template pTemplate="header">
        <tr><th>Exactly in</th><th style="width: 8rem">Genes</th></tr>
      </ng-template>
      <ng-template pTemplate="body" let-combo>
        <tr><td>{{ setsLabel(combo.sets) }}</td><td>{{ combo.size }}</td></tr>
      </ng-template>
    </p-table>

    <h4>{{ model.relation }}: {{ model.result.length }} genes</h4>
    <p-table [value]="model.result" styleClass="p-datatable-sm" [scrollable]="true" scrollHeight="320px">
      <ng-template pTemplate="header">
        <tr><th>Gene</th><th>Gene sets</th></tr>
      </ng-template>
      <ng-template pTemplate="body" let-gene>
        <tr><td>{{ gene.label }}</td><td>{{ setsLabel(gene.sets) }}</td></tr>
      </ng-template>
    </p-table>
  `,
  styles: ['.warn { border-left: 4px solid #F59E0B; }'],
})
export class VennComponent implements OnChanges {
  @Input({ required: true }) model!: BooleanModel;
  @ViewChild('chart', { static: true }) chart!: ElementRef<HTMLElement>;
  drawn = false;

  ngOnChanges(): void {
    this.drawn = this.draw();
  }

  setsLabel(sets: number[]): string {
    return sets.map(genesetLabel).join(' ∩ ');
  }

  download(): void {
    downloadSvg(this.chart.nativeElement, 'boolean-algebra-venn.svg');
  }

  /** Pairwise shared genes, from the exact combinations. */
  private shared(a: number, b: number): number {
    return this.model.combinations
      .filter((c) => c.sets.includes(a) && c.sets.includes(b))
      .reduce((sum, c) => sum + c.size, 0);
  }

  private draw(): boolean {
    const circles = vennLayout(this.model.sets, (a, b) => this.shared(a, b));
    if (!circles) {
      this.chart.nativeElement.innerHTML = '';
      return false;
    }
    const minX = Math.min(...circles.map((c) => c.x - c.r));
    const maxX = Math.max(...circles.map((c) => c.x + c.r));
    const minY = Math.min(...circles.map((c) => c.y - c.r));
    const maxY = Math.max(...circles.map((c) => c.y + c.r));
    const size = 460;
    // Room around the circles for the labels, which sit outside them.
    const pad = 70;
    const scale = (size - 2 * pad) / Math.max(maxX - minX, maxY - minY, 1e-9);
    const px = (x: number) => pad + (x - minX) * scale;
    const py = (y: number) => pad + (y - minY) * scale;
    // Each label goes just outside its circle, on the side facing away from the group, so it
    // never lands inside another set's circle.
    const cx = circles.reduce((sum, c) => sum + c.x, 0) / circles.length;
    const cy = circles.reduce((sum, c) => sum + c.y, 0) / circles.length;
    const outward = (c: (typeof circles)[number]) => {
      const dx = c.x - cx;
      const dy = c.y - cy;
      const length = Math.hypot(dx, dy);
      if (length < 1e-9) {
        // At the centroid (identical sets drawn on top of each other): no direction points
        // away, so spread the labels evenly around the circle by index, starting left.
        const angle = Math.PI + (2 * Math.PI * circles.indexOf(c)) / circles.length;
        return { dx: Math.cos(angle), dy: Math.sin(angle) };
      }
      return { dx: dx / length, dy: dy / length };
    };

    const host = this.chart.nativeElement;
    const svg = freshSvg(host, size, size, 'Venn diagram of the gene sets');
    const tooltip = new ChartTooltip(host);
    const g = svg.append('g').selectAll('g').data(circles).join('g');
    const discs = g
      .append('circle')
      .attr('cx', (c) => px(c.x))
      .attr('cy', (c) => py(c.y))
      .attr('r', (c) => c.r * scale)
      .attr('fill', (_, i) => schemeTableau10[i])
      .attr('fill-opacity', 0.25)
      .attr('stroke', (_, i) => schemeTableau10[i])
      .attr('stroke-width', 2);
    g.append('text')
      .attr('x', (c) => px(c.x) + outward(c).dx * (c.r * scale + 8))
      .attr('y', (c) => py(c.y) + outward(c).dy * (c.r * scale + 8) + 4)
      .attr('text-anchor', (c) => (outward(c).dx > 0.3 ? 'start' : outward(c).dx < -0.3 ? 'end' : 'middle'))
      .attr('fill', (_, i) => schemeTableau10[i])
      .attr('pointer-events', 'none')
      .style('font-weight', '600')
      .text((c) => `${genesetLabel(c.id)} (${c.size})`);

    const unique = (id: number) =>
      this.model.combinations.find((c) => c.sets.length === 1 && c.sets[0] === id)?.size ?? 0;
    const inAll = this.model.combinations.find((c) => c.sets.length === circles.length)?.size ?? 0;
    interactive(
      discs,
      tooltip,
      (circle) => ({
        title: genesetLabel(circle.id),
        rows: [
          { label: 'Genes', value: String(circle.size) },
          { label: 'Only in this set', value: String(unique(circle.id)) },
          ...circles
            .filter((other) => other.id !== circle.id)
            .map((other) => ({
              label: `Shared with ${genesetLabel(other.id)}`,
              value: String(this.shared(circle.id, other.id)),
            })),
          ...(circles.length === 3 ? [{ label: 'In all three', value: String(inAll) }] : []),
        ],
        note: 'Circle areas are proportional to set sizes, and overlaps to shared genes.',
      }),
      (circle) =>
        discs
          .attr('fill-opacity', (c) => (c === circle ? 0.55 : 0.12))
          .attr('stroke-width', (c) => (c === circle ? 3 : 1)),
      () => discs.attr('fill-opacity', 0.25).attr('stroke-width', 2),
    );
    return true;
  }
}
