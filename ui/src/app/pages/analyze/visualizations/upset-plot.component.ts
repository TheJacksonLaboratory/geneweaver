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

import {
  ACCENT,
  ChartTooltip,
  DIMMED,
  downloadSvg,
  freshSvg,
  interactive,
  MUTED,
  percent,
} from './chart-utils';
import { genesetLabel, UpSetModel } from './models';

/**
 * UpSet plot: one column per exclusive combination of gene sets, its size as a bar above
 * and its members as filled dots below; each gene set's size as a bar on the left.
 * Readable where a Venn diagram is not -- any number of sets.
 *
 * Hovering (or focusing) a column highlights its bar, its member sets and their rows;
 * hovering a gene set highlights every combination that includes it.
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
    const { sets, bars, total } = this.model;
    const host = this.chart.nativeElement;
    const left = 170;
    const top = 170;
    const row = 22;
    const col = Math.max(16, Math.min(28, 640 / Math.max(1, bars.length)));
    const width = left + col * bars.length + 20;
    const height = top + row * sets.length + 10;
    const svg = freshSvg(host, width, height, 'UpSet plot of gene set intersections');
    const tooltip = new ChartTooltip(host);

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

    // Row stripes behind the dots, so a hovered gene set reads across the whole matrix.
    const stripes = svg
      .append('g')
      .selectAll('rect')
      .data(sets)
      .join('rect')
      .attr('x', 0)
      .attr('y', (s) => yRow(s.id) ?? 0)
      .attr('width', width)
      .attr('height', yRow.bandwidth())
      .attr('fill', '#F1F5F9')
      .attr('opacity', 0);

    const columns = svg
      .append('g')
      .selectAll('g')
      .data(bars)
      .join('g')
      .attr('class', 'column')
      .attr('transform', (_, i) => `translate(${x(i)},0)`);
    columns
      .append('rect')
      .attr('class', 'bar')
      .attr('y', (b) => yBar(b.size))
      .attr('width', x.bandwidth())
      .attr('height', (b) => yBar(0) - yBar(b.size))
      .attr('fill', ACCENT);
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
    // A transparent hit area over each whole column: easier to hover than a thin bar.
    const hits = columns
      .append('rect')
      .attr('class', 'hit')
      .attr('x', 0)
      .attr('y', 0)
      .attr('width', x.bandwidth())
      .attr('height', height)
      .attr('fill', 'transparent');

    // Gene set labels and their sizes.
    const labels = svg
      .append('g')
      .selectAll('g')
      .data(sets)
      .join('g')
      .attr('class', 'set')
      .attr('transform', (s) => `translate(0,${yRow(s.id)})`);
    labels
      .append('rect')
      .attr('x', 80)
      .attr('y', 4)
      .attr('width', (s) => setWidth(s.size))
      .attr('height', yRow.bandwidth() - 8)
      .attr('fill', MUTED);
    labels
      .append('text')
      .attr('x', 4)
      .attr('y', yRow.bandwidth() / 2 + 4)
      .text((s) => genesetLabel(s.id));
    const setHits = labels
      .append('rect')
      .attr('width', left - 4)
      .attr('height', yRow.bandwidth())
      .attr('fill', 'transparent');

    const clear = () => {
      columns.attr('opacity', 1);
      labels.attr('opacity', 1);
      stripes.attr('opacity', 0);
    };
    interactive(
      hits,
      tooltip,
      (bar) => ({
        title: bar.sets.map(genesetLabel).join(' ∩ '),
        rows: [
          { label: 'Genes in exactly these sets', value: String(bar.size) },
          { label: 'Share of all genes', value: percent(bar.size, total) },
        ],
        note:
          bar.sets.length === 1
            ? `Genes found only in ${genesetLabel(bar.sets[0])}.`
            : `In all ${bar.sets.length} of these sets, and in none of the others.`,
      }),
      (bar) => {
        columns.attr('opacity', (b) => (b === bar ? 1 : DIMMED));
        labels.attr('opacity', (s) => (bar.sets.includes(s.id) ? 1 : DIMMED));
        stripes.attr('opacity', (s) => (bar.sets.includes(s.id) ? 1 : 0));
      },
      clear,
    );
    interactive(
      setHits,
      tooltip,
      (set) => ({
        title: genesetLabel(set.id),
        rows: [
          { label: 'Genes', value: String(set.size) },
          { label: 'Only in this set', value: `${set.unique} (${percent(set.unique, set.size)})` },
          { label: 'Shared with another set', value: String(Math.max(0, set.size - set.unique)) },
        ],
        note: 'Highlighting every combination that includes this set.',
      }),
      (set) => {
        columns.attr('opacity', (b) => (b.sets.includes(set.id) ? 1 : DIMMED));
        labels.attr('opacity', (s) => (s === set ? 1 : DIMMED));
        stripes.attr('opacity', (s) => (s === set ? 1 : 0));
      },
      clear,
    );
  }
}
