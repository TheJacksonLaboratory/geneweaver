import { NgFor } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
} from '@angular/core';
import { axisBottom, axisLeft, max, scaleLinear } from 'd3';

import { ACCENT, HIGHLIGHT, downloadSvg, freshSvg } from './chart-utils';
import { MsetModel } from './models';

/**
 * MSET: how often each overlap size came up when genes were drawn at random from the
 * universe (the null distribution), with the observed overlap marked. The further right of
 * the bars the mark sits, the more the overlap exceeds chance.
 */
@Component({
  selector: 'app-mset-histogram',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgFor],
  template: `
    <div #chart></div>
    <button type="button" class="p-button p-button-sm p-button-text" (click)="download()">
      Download SVG
    </button>
    <dl class="grid text-sm mt-2">
      <ng-container *ngFor="let item of model.summary">
        <dt class="col-6 md:col-3 font-semibold">{{ item.label }}</dt>
        <dd class="col-6 md:col-3 m-0">{{ item.value }}</dd>
      </ng-container>
    </dl>
  `,
})
export class MsetHistogramComponent implements OnChanges {
  @Input({ required: true }) model!: MsetModel;
  @ViewChild('chart', { static: true }) chart!: ElementRef<HTMLElement>;

  ngOnChanges(): void {
    this.draw();
  }

  download(): void {
    downloadSvg(this.chart.nativeElement, 'mset.svg');
  }

  private draw(): void {
    const { bins, observed, pValue, trials } = this.model;
    const width = 620;
    const height = 280;
    const m = { top: 30, right: 20, bottom: 40, left: 50 };
    const svg = freshSvg(
      this.chart.nativeElement,
      width,
      height,
      `MSET null distribution over ${trials} trials, observed overlap ${observed}`,
    );

    const xMax = Math.max(max(bins, (b) => b.overlap) ?? 0, observed ?? 0) + 1;
    // From -1, so the overlap-0 bar sits clear of the y axis rather than on it.
    const x = scaleLinear().domain([-1, xMax]).range([m.left, width - m.right]);
    const y = scaleLinear()
      .domain([0, max(bins, (b) => b.share) ?? 1])
      .nice()
      .range([height - m.bottom, m.top]);
    const barWidth = Math.max(2, x(1) - x(0) - 1);

    svg
      .append('g')
      .selectAll('rect')
      .data(bins)
      .join('rect')
      .attr('x', (b) => x(b.overlap) - barWidth / 2)
      .attr('y', (b) => y(b.share))
      .attr('width', barWidth)
      .attr('height', (b) => y(0) - y(b.share))
      .attr('fill', ACCENT)
      .append('title')
      .text((b) => `Overlap ${b.overlap}: ${(b.share * 100).toFixed(1)}% of random trials`);

    if (observed !== null) {
      svg
        .append('line')
        .attr('x1', x(observed))
        .attr('x2', x(observed))
        .attr('y1', m.top - 10)
        .attr('y2', height - m.bottom)
        .attr('stroke', HIGHLIGHT)
        .attr('stroke-width', 2)
        .append('title')
        .text(`Observed overlap: ${observed}`);
      svg
        .append('text')
        .attr('x', x(observed))
        .attr('y', m.top - 14)
        .attr('text-anchor', 'end')
        .attr('fill', HIGHLIGHT)
        .text(`observed ${observed} (p ${pValue})`);
    }

    svg
      .append('g')
      .attr('transform', `translate(0,${height - m.bottom})`)
      .call(axisBottom(x).ticks(Math.min(10, xMax)));
    svg
      .append('g')
      .attr('transform', `translate(${m.left},0)`)
      .call(axisLeft(y).ticks(5, '%'));
    svg
      .append('text')
      .attr('x', width / 2)
      .attr('y', height - 6)
      .attr('text-anchor', 'middle')
      .text('Genes shared by the two lists');
  }
}
