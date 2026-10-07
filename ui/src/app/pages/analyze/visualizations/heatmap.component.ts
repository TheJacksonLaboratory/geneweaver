import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
} from '@angular/core';
import { scaleBand } from 'd3';

import { downloadSvg, freshSvg, sequential } from './chart-utils';
import { genesetLabel, MatrixModel } from './models';

/**
 * A gene set x gene set matrix, shaded by the pair's statistic (Jaccard index for
 * JaccardSimilarity, -log10 p for HyperGeometric), with the value in each cell and the
 * full detail -- p-value, shared genes -- in its tooltip.
 */
@Component({
  selector: 'app-heatmap',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div #chart></div>
    <button type="button" class="p-button p-button-sm p-button-text" (click)="download()">
      Download SVG
    </button>
  `,
})
export class HeatmapComponent implements OnChanges {
  @Input({ required: true }) model!: MatrixModel;
  @Input() filename = 'matrix.svg';
  @ViewChild('chart', { static: true }) chart!: ElementRef<HTMLElement>;

  ngOnChanges(): void {
    this.draw();
  }

  download(): void {
    downloadSvg(this.chart.nativeElement, this.filename);
  }

  private draw(): void {
    const { ids, cells, domain, legend } = this.model;
    const cell = Math.max(36, Math.min(64, 480 / Math.max(1, ids.length)));
    const margin = 80;
    const size = cell * ids.length;
    const svg = freshSvg(this.chart.nativeElement, margin + size + 20, margin + size + 40, legend);

    const x = scaleBand<string>().domain(ids).range([margin, margin + size]);
    const y = scaleBand<string>().domain(ids).range([margin, margin + size]);
    const colour = sequential(domain);

    const g = svg.append('g').selectAll('g').data(cells).join('g');
    g.append('rect')
      .attr('x', (c) => x(c.col) ?? 0)
      .attr('y', (c) => y(c.row) ?? 0)
      .attr('width', x.bandwidth() - 1)
      .attr('height', y.bandwidth() - 1)
      .attr('fill', (c) => (c.value === null ? '#F1F5F9' : colour(c.value)))
      .append('title')
      .text((c) => c.detail);
    g.append('text')
      .attr('x', (c) => (x(c.col) ?? 0) + x.bandwidth() / 2)
      .attr('y', (c) => (y(c.row) ?? 0) + y.bandwidth() / 2 + 4)
      .attr('text-anchor', 'middle')
      .attr('fill', (c) =>
        c.value !== null && c.value > (domain[0] + domain[1]) / 2 ? 'white' : '#0F172A',
      )
      .text((c) => c.label);

    svg
      .append('g')
      .selectAll('text')
      .data(ids)
      .join('text')
      .attr('x', margin - 6)
      .attr('y', (id) => (y(id) ?? 0) + y.bandwidth() / 2 + 4)
      .attr('text-anchor', 'end')
      .text(genesetLabel);
    svg
      .append('g')
      .selectAll('text')
      .data(ids)
      .join('text')
      .attr('transform', (id) => `translate(${(x(id) ?? 0) + x.bandwidth() / 2},${margin - 6}) rotate(-45)`)
      .text(genesetLabel);
    svg
      .append('text')
      .attr('x', margin)
      .attr('y', margin + size + 24)
      .text(`Shading: ${legend} (${domain[0]} to ${domain[1].toFixed(1)}). Hover a cell for details.`);
  }
}
