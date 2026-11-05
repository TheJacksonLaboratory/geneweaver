import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
} from '@angular/core';
import { arc, schemeTableau10 } from 'd3';

import { ChartTooltip, DIMMED, downloadSvg, freshSvg, interactive } from './chart-utils';
import { DendrogramNode, SunburstArc, sunburstArcs } from './models';

const CLUSTER = '#CBD5E1';

/**
 * JaccardClustering as legacy's "partitioned sunburst": the tree from the centre out, each
 * cluster a grey arc spanning its gene sets and each gene set a coloured arc reaching the
 * rim. Hovering a cluster shows its Jaccard similarity in the centre and fades the gene sets
 * outside it.
 */
@Component({
  selector: 'app-sunburst',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div #chart></div>
    <button type="button" class="p-button p-button-sm p-button-text" (click)="download()">
      Download SVG
    </button>
  `,
})
export class SunburstComponent implements OnChanges {
  @Input({ required: true }) model!: DendrogramNode;
  @Input() method = '';
  @ViewChild('chart', { static: true }) chart!: ElementRef<HTMLElement>;

  ngOnChanges(): void {
    this.draw();
  }

  download(): void {
    downloadSvg(this.chart.nativeElement, 'jaccard-clustering-sunburst.svg');
  }

  private draw(): void {
    const arcs = sunburstArcs(this.model);
    const host = this.chart.nativeElement;
    const size = 560;
    const outer = 190;
    const hole = 48;
    const rings = Math.max(1, ...arcs.map((a) => a.depth));
    const ring = (outer - hole) / rings;
    const svg = freshSvg(
      host,
      size,
      size,
      `Sunburst of the gene set clustering${this.method ? ` (${this.method} linkage)` : ''}`,
    );
    const tooltip = new ChartTooltip(host);
    const g = svg.append('g').attr('transform', `translate(${size / 2},${size / 2})`);
    const leaves = arcs.filter((a) => a.leaf);
    const colour = (a: SunburstArc) =>
      a.leaf ? schemeTableau10[leaves.indexOf(a) % schemeTableau10.length] : CLUSTER;
    const shape = arc<SunburstArc>()
      .startAngle((a) => a.start)
      .endAngle((a) => a.end)
      .innerRadius((a) => hole + (a.depth - 1) * ring)
      // Gene sets reach the rim whatever their depth, so every one is labelled at the edge.
      .outerRadius((a) => (a.leaf ? outer : hole + a.depth * ring))
      .padAngle(0.004);

    const paths = g
      .append('g')
      .selectAll('path')
      .data(arcs)
      .join('path')
      .attr('d', shape)
      .attr('fill', colour)
      .attr('stroke', 'white')
      .attr('stroke-width', 2);

    // Gene set names outside the rim, turned to read outward from the centre.
    g.append('g')
      .selectAll('text')
      .data(leaves)
      .join('text')
      .attr('transform', (a) => {
        const angle = ((a.start + a.end) / 2) * (180 / Math.PI) - 90;
        const flip = angle > 90;
        return `rotate(${angle}) translate(${outer + 6},0)${flip ? ' rotate(180)' : ''}`;
      })
      .attr('text-anchor', (a) => (((a.start + a.end) / 2) * (180 / Math.PI) - 90 > 90 ? 'end' : 'start'))
      .attr('dy', '0.32em')
      .attr('pointer-events', 'none')
      .text((a) => a.name);

    // At rest the centre stands for the root, which has no ring of its own: where all join.
    const restTitle = 'All join at similarity';
    const restValue = (1 - this.model.height).toFixed(3);
    const centreTitle = g
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '-0.3em')
      .attr('fill', '#475569')
      .text(restTitle);
    const centreValue = g
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '1.1em')
      .style('font-size', '16px')
      .style('font-weight', '600')
      .text(restValue);

    interactive(
      paths,
      tooltip,
      (a) =>
        a.leaf
          ? {
              title: a.name,
              rows: [{ label: 'First joins at similarity', value: this.joinsAt(arcs, a) }],
            }
          : {
              title: `Cluster of ${a.members.length} gene sets`,
              rows: [
                { label: 'Jaccard similarity', value: (a.similarity ?? 0).toFixed(3) },
                { label: 'Gene sets', value: a.members.join(', ') },
              ],
            },
      (a) => {
        const inside = new Set(a.members);
        paths.attr('opacity', (o) => (o.members.every((m) => inside.has(m)) ? 1 : DIMMED));
        centreTitle.text(a.leaf ? a.name : 'Jaccard similarity');
        centreValue.text(a.leaf ? '' : (a.similarity ?? 0).toFixed(3));
      },
      () => {
        paths.attr('opacity', 1);
        centreTitle.text(restTitle);
        centreValue.text(restValue);
      },
    );
  }

  /** The similarity of the smallest cluster holding a gene set: where it first joins. */
  private joinsAt(arcs: SunburstArc[], leaf: SunburstArc): string {
    const parent = arcs
      .filter((a) => !a.leaf && a.members.includes(leaf.name))
      .sort((a, b) => a.members.length - b.members.length)[0];
    return parent ? (parent.similarity ?? 0).toFixed(3) : '—';
  }
}
