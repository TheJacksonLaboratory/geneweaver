import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
} from '@angular/core';
import { hierarchy, HierarchyCircularNode, pack, schemeTableau10, select } from 'd3';

import {
  ChartTooltip,
  DIMMED,
  downloadSvg,
  freshSvg,
  interactive,
  percent,
} from './chart-utils';
import { PackNode } from './models';

/**
 * DBSCAN's clusters as packed circles: one outer circle per cluster, one dot per gene in
 * it, coloured by cluster. Gene names are on the dots for small clusters and in the
 * tooltips for all. Click a cluster to zoom in, the background to zoom out.
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
    const host = this.chart.nativeElement;
    const size = 560;
    const svg = freshSvg(host, size, size, 'DBSCAN gene clusters');
    const tooltip = new ChartTooltip(host);
    const root = pack<PackNode>()
      .size([size - 4, size - 4])
      .padding((node) => (node.depth === 0 ? 10 : 2))(
      hierarchy(this.model).sum((node) => node.value ?? 0),
    );
    const colour = (index: number) => schemeTableau10[index % schemeTableau10.length];
    const clusters = root.children ?? [];
    const totalGenes = root.leaves().length;

    // A full-size background: clicking it zooms back out.
    const background = svg
      .append('rect')
      .attr('width', size)
      .attr('height', size)
      .attr('fill', 'transparent');
    const view = svg.append('g').attr('transform', 'translate(2,2)');
    const groups = view.selectAll('g').data(clusters).join('g');
    const outlines = groups
      .append('circle')
      .attr('cx', (c) => c.x)
      .attr('cy', (c) => c.y)
      .attr('r', (c) => c.r)
      .attr('fill', (_, i) => colour(i))
      .attr('fill-opacity', 0.12)
      .attr('stroke', (_, i) => colour(i));
    const genes = groups
      .selectAll<SVGCircleElement, HierarchyCircularNode<PackNode>>('circle.gene')
      .data((c) => c.children ?? [])
      .join('circle')
      .attr('class', 'gene')
      .attr('cx', (n) => n.x)
      .attr('cy', (n) => n.y)
      .attr('r', (n) => n.r)
      .attr('fill', (n) => colour(n.parent ? clusters.indexOf(n.parent) : 0));
    groups.each(function (clusterNode) {
      const g = select(this);
      const members = clusterNode.children ?? [];
      if (members.length <= 40) {
        g.selectAll('text.gene-label')
          .data(members)
          .join('text')
          .attr('class', 'gene-label')
          .attr('x', (n) => n.x)
          .attr('y', (n) => n.y + 3)
          .attr('text-anchor', 'middle')
          .attr('fill', 'white')
          .attr('pointer-events', 'none')
          .style('font-size', (n) => `${Math.max(6, Math.min(10, n.r / 2))}px`)
          .text((n) => n.data.name);
      }
      g.append('text')
        .attr('x', clusterNode.x)
        .attr('y', clusterNode.y - clusterNode.r - 3)
        .attr('text-anchor', 'middle')
        .attr('pointer-events', 'none')
        .style('font-weight', '600')
        .text(clusterNode.data.name);
    });

    // Click a cluster to zoom into it; click the background (or the same cluster) to zoom out.
    let focused: HierarchyCircularNode<PackNode> | null = null;
    const zoomTo = (target: HierarchyCircularNode<PackNode> | null) => {
      focused = target;
      const k = target ? (size - 20) / (2 * target.r) : 1;
      const tx = target ? size / 2 - target.x * k : 2;
      const ty = target ? size / 2 - target.y * k : 2;
      const transform = `translate(${tx},${ty}) scale(${k})`;
      // Which cluster is in view, set at once so the state never lags the animation.
      view.attr('data-focus', target ? target.data.name : null);
      // Respect a reduced-motion preference: jump rather than animate.
      const reduceMotion =
        typeof window.matchMedia === 'function' &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (reduceMotion) {
        view.attr('transform', transform);
      } else {
        view.transition().duration(500).attr('transform', transform);
      }
    };
    outlines.on('click', (event: MouseEvent, c) => {
      event.stopPropagation();
      zoomTo(focused === c ? null : c);
    });
    background.on('click', () => zoomTo(null));

    interactive(
      outlines,
      tooltip,
      (c) => {
        const members = c.children ?? [];
        return {
          title: c.data.name.replace(/ \(.*\)$/, ''),
          rows: [
            { label: 'Genes', value: String(members.length) },
            { label: 'Share of clustered genes', value: percent(members.length, totalGenes) },
          ],
          note: 'Click to zoom in; click the background to zoom out.',
        };
      },
      (c) => groups.attr('opacity', (o) => (o === c ? 1 : DIMMED)),
      () => groups.attr('opacity', 1),
    );
    interactive(
      genes,
      tooltip,
      (n) => ({
        title: n.data.name,
        rows: [{ label: 'Cluster', value: (n.parent?.data.name ?? '').replace(/ \(.*\)$/, '') }],
      }),
      (n) => groups.attr('opacity', (o) => (o === n.parent ? 1 : DIMMED)),
      () => groups.attr('opacity', 1),
    );
  }
}
