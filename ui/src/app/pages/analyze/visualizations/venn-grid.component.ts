import { NgFor } from '@angular/common';
import {
  AfterViewChecked,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
} from '@angular/core';
import { select, Selection } from 'd3';

import { ChartTooltip, downloadSvg, freshSvg, interactive } from './chart-utils';
import {
  genesetLabel,
  P_THRESHOLDS,
  vennCellGreyed,
  VennGridCell,
  VennGridModel,
} from './models';

/** Okabe-Ito colours: told apart with every common colour-vision deficiency. */
const ROW = '#D55E00';
const COL = '#0072B2';
const SAME = '#E69F00';
const GREY = '#CBD5E1';

/**
 * JaccardSimilarity as legacy drew it: a Venn diagram for every pair of gene sets, row set
 * against column set, with the shared counts, the Jaccard index and the p-value in each
 * cell. The p-value threshold greys the pairs that do not pass it. Hovering a cell gives the
 * pair's numbers and highlights its row and column.
 */
@Component({
  selector: 'app-venn-grid',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgFor],
  template: `
    <div class="flex align-items-center gap-2 mb-2 text-sm">
      <label for="venn-grid-threshold">p-value threshold</label>
      <select
        #thresholdSelect
        id="venn-grid-threshold"
        class="p-inputtext p-inputtext-sm"
        (change)="setThreshold($any($event.target).value)"
      >
        <option *ngFor="let t of thresholds" [value]="t">
          {{ t === 1 ? '1.0 (show all)' : t }}
        </option>
      </select>
      <span class="text-color-secondary" aria-live="polite">{{ greyedNote }}</span>
    </div>
    <div #chart></div>
    <button type="button" class="p-button p-button-sm p-button-text" (click)="download()">
      Download SVG
    </button>
  `,
})
export class VennGridComponent implements OnChanges, AfterViewChecked {
  @Input({ required: true }) model!: VennGridModel;
  @ViewChild('chart', { static: true }) chart!: ElementRef<HTMLElement>;
  @ViewChild('thresholdSelect', { static: true }) thresholdSelect!: ElementRef<HTMLSelectElement>;

  threshold = 1;
  thresholds: number[] = P_THRESHOLDS;
  greyedNote = '';
  private groups?: Selection<SVGGElement, VennGridCell, SVGGElement, unknown>;

  ngOnChanges(): void {
    this.threshold = this.model.threshold;
    this.thresholds = [...new Set([...P_THRESHOLDS, this.model.threshold])].sort((a, b) => b - a);
    this.draw();
    this.shade();
  }

  /**
   * Show the current threshold in the select, once its options exist: a value set before
   * they render names no option, and the select would show 1.0 over a grid shaded at the
   * run's threshold.
   */
  ngAfterViewChecked(): void {
    const select = this.thresholdSelect.nativeElement;
    if (select.value !== String(this.threshold)) {
      select.value = String(this.threshold);
    }
  }

  setThreshold(value: string): void {
    // Only a listed threshold: a change event can carry "" (no option selected), which
    // Number() would turn into a threshold of 0 that greys every pair.
    const threshold = Number(value);
    if (value === '' || !this.thresholds.includes(threshold)) {
      return;
    }
    this.threshold = threshold;
    this.shade();
  }

  download(): void {
    downloadSvg(this.chart.nativeElement, 'jaccard-similarity-venn.svg');
  }

  /** Grey the pairs that do not pass the threshold, without redrawing. */
  private shade(): void {
    const greyed = (cell: VennGridCell) => vennCellGreyed(cell, this.threshold);
    this.groups
      ?.attr('data-greyed', (cell) => (greyed(cell) ? 'true' : null))
      .selectAll<SVGCircleElement, { role: string; cell: VennGridCell }>('circle')
      .attr('fill', (c) => (greyed(c.cell) ? GREY : c.role === 'row' ? ROW : c.role === 'col' ? COL : SAME));
    const count = this.model.cells.filter(greyed).length / 2;
    this.greyedNote =
      this.threshold >= 1
        ? 'All pairs shown.'
        : `${count} of ${this.pairs()} pairs greyed: p above ${this.threshold}, or no p-value.`;
  }

  private pairs(): number {
    const n = this.model.ids.length;
    return (n * (n - 1)) / 2;
  }

  private draw(): void {
    const { ids, cells } = this.model;
    const host = this.chart.nativeElement;
    const cell = Math.max(96, Math.min(150, 760 / Math.max(1, ids.length)));
    const left = 90;
    const top = 40;
    const legendHeight = 46;
    const size = cell * ids.length;
    const svg = freshSvg(
      host,
      left + size + 10,
      top + size + legendHeight,
      `Venn diagram of each pair of ${ids.length} gene sets, with Jaccard index and p-value`,
    );
    const tooltip = new ChartTooltip(host);
    const index = new Map(ids.map((id, i) => [id, i]));

    const groups = svg
      .append('g')
      .selectAll<SVGGElement, VennGridCell>('g')
      .data(cells)
      .join('g')
      .attr('class', 'cell')
      .attr(
        'transform',
        (c) => `translate(${left + (index.get(c.col) ?? 0) * cell},${top + (index.get(c.row) ?? 0) * cell})`,
      );
    this.groups = groups;
    const frames = groups
      .append('rect')
      .attr('width', cell - 2)
      .attr('height', cell - 2)
      .attr('fill', (c) => (c.diagonal ? '#F8FAFC' : 'white'))
      .attr('stroke', '#E2E8F0');
    // Circles sit in the upper part of the cell, the text below them.
    const disc = cell * 0.62;
    groups
      .selectAll('circle')
      .data((c) => c.circles.map((circle) => ({ ...circle, cell: c })))
      .join('circle')
      .attr('cx', (c) => c.cx * (cell - 2))
      .attr('cy', (c) => c.cy * disc + 2)
      .attr('r', (c) => c.r * disc)
      .attr('fill-opacity', 0.55)
      .attr('stroke', '#0F172A')
      .attr('stroke-width', 0.75)
      .attr('pointer-events', 'none');
    groups.each(function (c) {
      select(this)
        .selectAll('text')
        .data(c.lines)
        .join('text')
        .attr('x', (cell - 2) / 2)
        .attr('y', (_, i) => disc + 14 + i * 12)
        .attr('text-anchor', 'middle')
        .attr('pointer-events', 'none')
        .style('font-size', '10px')
        .text((line) => line);
    });

    const rowLabels = svg
      .append('g')
      .selectAll('text')
      .data(ids)
      .join('text')
      .attr('x', left - 8)
      .attr('y', (_, i) => top + i * cell + cell / 2)
      .attr('text-anchor', 'end')
      .attr('fill', ROW)
      .text(genesetLabel);
    const colLabels = svg
      .append('g')
      .selectAll('text')
      .data(ids)
      .join('text')
      .attr('x', (_, i) => left + i * cell + cell / 2)
      .attr('y', top - 10)
      .attr('text-anchor', 'middle')
      .attr('fill', COL)
      .text(genesetLabel);

    const legend = svg.append('g').attr('transform', `translate(${left},${top + size + 18})`);
    const items: [string, string][] = [
      [ROW, 'Row gene set'],
      [COL, 'Column gene set'],
      [SAME, 'Same gene set'],
      [GREY, 'Above the p-value threshold, or no p-value'],
    ];
    let x = 0;
    for (const [colour, text] of items) {
      legend.append('circle').attr('cx', x + 6).attr('cy', 0).attr('r', 6).attr('fill', colour).attr('fill-opacity', 0.55);
      legend.append('text').attr('x', x + 16).attr('y', 4).text(text);
      x += 26 + text.length * 6;
    }
    legend
      .append('text')
      .attr('y', 22)
      .attr('fill', '#475569')
      .text('Counts are (only in row · shared · only in column). Hover or tab to a cell for details.');

    interactive(
      frames,
      tooltip,
      (c) => {
        const content = c.tooltip;
        if (!vennCellGreyed(c, this.threshold) || c.diagonal) {
          return content;
        }
        const why = c.p === null ? 'no p-value' : `p above ${this.threshold}`;
        return { ...content, title: `${content.title} (greyed: ${why})` };
      },
      (c) => {
        groups.attr('opacity', (o) => (o.row === c.row || o.col === c.col ? 1 : 0.35));
        frames.attr('stroke', (o) => (o === c ? '#0F172A' : '#E2E8F0'));
        rowLabels.style('font-weight', (id) => (id === c.row ? '700' : '400'));
        colLabels.style('font-weight', (id) => (id === c.col ? '700' : '400'));
      },
      () => {
        groups.attr('opacity', 1);
        frames.attr('stroke', '#E2E8F0');
        rowLabels.style('font-weight', '400');
        colLabels.style('font-weight', '400');
      },
    );
  }
}
