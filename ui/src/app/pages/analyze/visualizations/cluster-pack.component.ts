import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
} from '@angular/core';
import { hierarchy, pack, schemeTableau10, select } from 'd3';

import { downloadSvg, freshSvg } from './chart-utils';
import { PackNode } from './models';

/**
 * DBSCAN's clusters as packed circles: one outer circle per cluster, one dot per gene in
 * it, coloured by cluster. Gene names are in the tooltips and, for small clusters, on the
 * dots.
 */
@Component({
  selector: 'app-cluster-pack',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div #chart></div>
    <button type="button" class="p-button p-button-sm p-button-text" (click)="download()">
      Download SVG
    </button>
  `,
})
export class ClusterPackComponent implements OnChanges {
  @Input({ required: true }) model!: PackNode;
  @ViewChild('chart', { static: true }) chart!: ElementRef<HTMLElement>;

  ngOnChanges(): void {
    this.draw();
  }

  download(): void {
    downloadSvg(this.chart.nativeElement, 'dbscan-clusters.svg');
  }

  private draw(): void {
    const size = 560;
    const svg = freshSvg(this.chart.nativeElement, size, size, 'DBSCAN gene clusters');
    const root = pack<PackNode>()
      .size([size - 4, size - 4])
      .padding((node) => (node.depth === 0 ? 10 : 2))(
      hierarchy(this.model).sum((node) => node.value ?? 0),
    );
    const colour = (index: number) => schemeTableau10[index % schemeTableau10.length];

    const clusters = root.children ?? [];
    const groups = svg
      .append('g')
      .attr('transform', 'translate(2,2)')
      .selectAll('g')
      .data(clusters)
      .join('g');
    groups
      .append('circle')
      .attr('cx', (c) => c.x)
      .attr('cy', (c) => c.y)
      .attr('r', (c) => c.r)
      .attr('fill', (_, i) => colour(i))
      .attr('fill-opacity', 0.12)
      .attr('stroke', (_, i) => colour(i))
      .append('title')
      .text((c) => c.data.name);
    groups.each(function (clusterNode, index) {
      const genes = clusterNode.children ?? [];
      const g = select(this);
      const dots = g.selectAll('g.gene').data(genes).join('g').attr('class', 'gene');
      dots
        .append('circle')
        .attr('cx', (n) => n.x)
        .attr('cy', (n) => n.y)
        .attr('r', (n) => n.r)
        .attr('fill', colour(index))
        .append('title')
        .text((n) => n.data.name);
      if (genes.length <= 40) {
        dots
          .append('text')
          .attr('x', (n) => n.x)
          .attr('y', (n) => n.y + 3)
          .attr('text-anchor', 'middle')
          .attr('fill', 'white')
          .style('font-size', (n) => `${Math.max(6, Math.min(10, n.r / 2))}px`)
          .text((n) => n.data.name);
      }
      g.append('text')
        .attr('x', clusterNode.x)
        .attr('y', clusterNode.y - clusterNode.r - 3)
        .attr('text-anchor', 'middle')
        .style('font-weight', '600')
        .text(clusterNode.data.name);
    });
  }
}
