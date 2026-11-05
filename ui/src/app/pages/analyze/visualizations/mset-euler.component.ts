import { NgFor, NgIf } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
} from '@angular/core';

import { ChartTooltip, downloadSvg, freshSvg, interactive, MUTED, percent } from './chart-utils';
import { MsetEuler } from './models';

/** Okabe-Ito, as in the Venn grid: list 1 vermilion, list 2 blue. */
const LIST1 = '#D55E00';
const LIST2 = '#0072B2';

interface Disc {
  key: 'universe' | 'list1' | 'list2';
  x: number;
  y: number;
  r: number;
  colour: string;
}

/**
 * MSET's size comparison, as legacy drew it: the universe as a circle containing both lists,
 * every area proportional to its gene count. Lists are a small share of a universe of tens of
 * thousands of genes, so a magnified copy of the two beside it shows their overlap -- the
 * lens is proportional to the shared genes. The shared genes are listed underneath.
 */
@Component({
  selector: 'app-mset-euler',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIf, NgFor],
  template: `
    <div #chart></div>
    <button type="button" class="p-button p-button-sm p-button-text" (click)="download()">
      Download SVG
    </button>
    <h4 class="mb-2">Shared genes ({{ genes.length }})</h4>
    <ng-container *ngIf="genes.length">
      <label class="block text-sm mb-1" for="mset-gene-filter">Filter shared genes</label>
      <input
        id="mset-gene-filter"
        class="p-inputtext p-inputtext-sm mb-2"
        type="search"
        [value]="filter"
        (input)="filter = $any($event.target).value"
      />
      <p class="text-sm text-color-secondary m-0 mb-1" aria-live="polite">
        {{ shown.length === genes.length ? genes.length + ' genes' : shown.length + ' of ' + genes.length + ' genes' }}
      </p>
      <ul class="genes list-none p-2 m-0 surface-50 border-round text-sm">
        <li *ngFor="let gene of shown">{{ gene }}</li>
      </ul>
    </ng-container>
  `,
  styles: [
    '.genes { max-height: 12rem; overflow: auto; columns: 8rem; column-gap: 1rem; }',
  ],
})
export class MsetEulerComponent implements OnChanges {
  @Input({ required: true }) model!: MsetEuler;
  @Input() genes: string[] = [];
  @ViewChild('chart', { static: true }) chart!: ElementRef<HTMLElement>;
  filter = '';

  get shown(): string[] {
    const term = this.filter.trim().toLowerCase();
    return term ? this.genes.filter((gene) => gene.toLowerCase().includes(term)) : this.genes;
  }

  ngOnChanges(): void {
    this.draw();
  }

  download(): void {
    downloadSvg(this.chart.nativeElement, 'mset-size-comparison.svg');
  }

  private draw(): void {
    const m = this.model;
    const host = this.chart.nativeElement;
    const width = 620;
    const height = 300;
    const universeR = 120;
    const svg = freshSvg(
      host,
      width,
      height,
      `Size comparison: list 1 of ${m.list1} genes and list 2 of ${m.list2} genes, sharing ${m.shared}, in a universe of ${m.universe}`,
    );
    const tooltip = new ChartTooltip(host);

    // Left: to scale in the universe. Right: the two lists magnified so the larger fills 80px.
    const left = { x: 20 + universeR, y: 150 };
    const right = { x: 460, y: 150 };
    // Pixels per unit (universe radius = 1) for the magnified pair: the larger list at most
    // 80px, and the pair's whole width within 220px however far apart they sit.
    const halfWidth = m.distance / 2 + Math.max(m.r1, m.r2);
    const k = Math.min(80 / Math.max(m.r1, m.r2, 1e-9), 110 / Math.max(halfWidth, 1e-9));
    const magnify = k / universeR;
    const pair = (centre: { x: number; y: number }, k: number): Disc[] => [
      { key: 'list1', x: centre.x - (m.distance / 2) * k, y: centre.y, r: m.r1 * k, colour: LIST1 },
      { key: 'list2', x: centre.x + (m.distance / 2) * k, y: centre.y, r: m.r2 * k, colour: LIST2 },
    ];
    const discs: Disc[] = [
      { key: 'universe', x: left.x, y: left.y, r: universeR, colour: MUTED },
      ...pair(left, universeR),
      ...pair(right, universeR * magnify),
    ];

    // The magnified pair's frame, tied back to where it sits in the universe.
    const zoomR = Math.max(m.r1, m.r2) * universeR + Math.abs(m.distance / 2) * universeR + 3;
    svg
      .append('circle')
      .attr('cx', left.x)
      .attr('cy', left.y)
      .attr('r', zoomR)
      .attr('fill', 'none')
      .attr('stroke', '#475569')
      .attr('stroke-dasharray', '3 2');
    svg
      .append('line')
      .attr('x1', left.x + zoomR)
      .attr('y1', left.y)
      .attr('x2', right.x - halfWidth * k - 6)
      .attr('y2', right.y)
      .attr('stroke', '#475569')
      .attr('stroke-dasharray', '3 2');

    const marks = svg
      .append('g')
      .selectAll('circle')
      .data(discs)
      .join('circle')
      .attr('cx', (d) => d.x)
      .attr('cy', (d) => d.y)
      .attr('r', (d) => Math.max(d.r, 0.5))
      .attr('fill', (d) => d.colour)
      .attr('fill-opacity', (d) => (d.key === 'universe' ? 0.15 : 0.45))
      .attr('stroke', (d) => d.colour);

    svg
      .append('text')
      .attr('x', left.x)
      .attr('y', 18)
      .attr('text-anchor', 'middle')
      .style('font-weight', '600')
      .text('To scale');
    svg
      .append('text')
      .attr('x', right.x)
      .attr('y', 18)
      .attr('text-anchor', 'middle')
      .style('font-weight', '600')
      .text(`The two lists, magnified ×${Math.round(magnify)}`);

    const legend = svg.append('g').attr('transform', `translate(330,${height - 54})`);
    const items: [string, string][] = [
      [MUTED, `Universe: ${m.universe.toLocaleString()} genes`],
      [LIST1, `List 1: ${m.list1} genes`],
      [LIST2, `List 2: ${m.list2} genes`],
    ];
    items.forEach(([colour, text], i) => {
      legend.append('circle').attr('cx', 6).attr('cy', i * 16).attr('r', 6).attr('fill', colour).attr('fill-opacity', 0.45);
      legend.append('text').attr('x', 16).attr('y', i * 16 + 4).text(text);
    });
    legend.append('text').attr('x', 0).attr('y', 3 * 16 + 4).text(`Shared: ${m.shared} genes`);

    const shareOf = (n: number) => percent(n, m.universe);
    interactive(marks, tooltip, (d) => {
      if (d.key === 'universe') {
        return {
          title: 'Universe',
          rows: [{ label: 'Genes', value: m.universe.toLocaleString() }],
          note: 'The genes random lists are drawn from.',
        };
      }
      const [size, other] = d.key === 'list1' ? [m.list1, m.list2] : [m.list2, m.list1];
      return {
        title: d.key === 'list1' ? 'List 1' : 'List 2',
        rows: [
          { label: 'Genes in the universe', value: String(size) },
          { label: 'Share of the universe', value: shareOf(size) },
          { label: 'Shared with the other list', value: String(m.shared) },
          { label: 'Share of this list shared', value: percent(m.shared, size) },
          { label: 'Other list', value: `${other} genes` },
        ],
      };
    });
  }
}
