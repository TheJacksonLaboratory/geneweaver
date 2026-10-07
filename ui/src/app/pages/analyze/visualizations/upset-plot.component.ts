import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
} from '@angular/core';
import { NgIf } from '@angular/common';
import { axisLeft, max, scaleBand, scaleLinear, select } from 'd3';

import { ACCENT, MUTED, downloadSvg, freshSvg } from './chart-utils';
import { genesetLabel, UpSetModel } from './models';

/**
 * UpSet plot: one column per exclusive combination of gene sets, its size as a bar above
 * and its members as filled dots below; each gene set's size as a bar on the left.
 * Readable where a Venn diagram is not -- any number of sets.
 */
@Component({
  selector: 'app-upset-plot',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div #chart></div>
    <p *ngIf="model.hidden" class="text-sm text-color-secondary">
      Showing the {{ model.bars.length }} largest combinations; {{ model.hidden }} smaller ones
      are in the table below.
    </p>
    <button type="button" class="p-button p-button-sm p-button-text" (click)="download()">
      Download SVG
    </button>
  `,
  imports: [NgIf],
})
export class UpsetPlotComponent implements OnChanges {
  @Input({ required: true }) model!: UpSetModel;
  @ViewChild('chart', { static: true }) chart!: ElementRef<HTMLElement>;

  ngOnChanges(): void {
    this.draw();
  }

  download(): void {
    downloadSvg(this.chart.nativeElement, 'upset.svg');
  }

  private draw(): void {
    const { sets, bars } = this.model;
    const left = 170;
    const top = 170;
    const row = 22;
    const col = Math.max(16, Math.min(28, 640 / Math.max(1, bars.length)));
    const width = left + col * bars.length + 20;
    const height = top + row * sets.length + 10;
    const svg = freshSvg(this.chart.nativeElement, width, height, 'UpSet plot of gene set intersections');

    const x = scaleBand<number>()
      .domain(bars.map((_, i) => i))
      .range([left, left + col * bars.length])
      .padding(0.2);
    const yBar = scaleLinear()
      .domain([0, max(bars, (b) => b.size) ?? 1])
      .nice()
      .range([top - 10, 22]);
    const yRow = scaleBand<string>()
      .domain(sets.map((s) => s.id))
      .range([top, top + row * sets.length]);
    const setWidth = scaleLinear()
      .domain([0, max(sets, (s) => s.size) ?? 1])
      .range([0, 70]);

    svg.append('g').attr('transform', `translate(${left},0)`).call(axisLeft(yBar).ticks(4));

    const columns = svg
      .append('g')
      .selectAll('g')
      .data(bars)
      .join('g')
      .attr('transform', (_, i) => `translate(${x(i)},0)`);
    columns
      .append('rect')
      .attr('y', (b) => yBar(b.size))
      .attr('width', x.bandwidth())
      .attr('height', (b) => yBar(0) - yBar(b.size))
      .attr('fill', ACCENT)
      .append('title')
      .text((b) => `${b.sets.map(genesetLabel).join(' ∩ ')} only: ${b.size} genes`);
    columns
      .append('text')
      .attr('x', x.bandwidth() / 2)
      .attr('y', (b) => yBar(b.size) - 3)
      .attr('text-anchor', 'middle')
      .text((b) => b.size);

    // Membership dots, joined by a line where a column spans several sets.
    const r = Math.min(6, x.bandwidth() / 2);
    columns.each(function (bar) {
      const column = select(this);
      const ys = bar.sets.map((id) => (yRow(id) ?? 0) + yRow.bandwidth() / 2);
      if (ys.length > 1) {
        column
          .append('line')
          .attr('x1', x.bandwidth() / 2)
          .attr('x2', x.bandwidth() / 2)
          .attr('y1', Math.min(...ys))
          .attr('y2', Math.max(...ys))
          .attr('stroke', '#334155')
          .attr('stroke-width', 2);
      }
      column
        .selectAll('circle')
        .data(sets)
        .join('circle')
        .attr('cx', x.bandwidth() / 2)
        .attr('cy', (s) => (yRow(s.id) ?? 0) + yRow.bandwidth() / 2)
        .attr('r', r)
        .attr('fill', (s) => (bar.sets.includes(s.id) ? '#334155' : '#E2E8F0'));
    });

    // Gene set labels and their sizes.
    const labels = svg
      .append('g')
      .selectAll('g')
      .data(sets)
      .join('g')
      .attr('transform', (s) => `translate(0,${yRow(s.id)})`);
    labels
      .append('rect')
      .attr('x', 80)
      .attr('y', 4)
      .attr('width', (s) => setWidth(s.size))
      .attr('height', yRow.bandwidth() - 8)
      .attr('fill', MUTED)
      .append('title')
      .text((s) => `${genesetLabel(s.id)}: ${s.size} genes`);
    labels
      .append('text')
      .attr('x', 4)
      .attr('y', yRow.bandwidth() / 2 + 4)
      .text((s) => genesetLabel(s.id));
  }
}
