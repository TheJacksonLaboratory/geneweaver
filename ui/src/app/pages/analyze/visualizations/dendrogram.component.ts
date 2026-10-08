import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
} from '@angular/core';
import { axisBottom, cluster, hierarchy, HierarchyPointNode, scaleLinear } from 'd3';

import { ACCENT, ChartTooltip, DIMMED, downloadSvg, freshSvg, interactive } from './chart-utils';
import { DendrogramNode } from './models';

/**
 * JaccardClustering's tree, drawn horizontally: leaves (gene sets) on the right, each merge
 * placed at its Jaccard distance on the x axis, so a merge further left joins more
 * dissimilar clusters. Hovering a merge highlights the cluster it forms; hovering a gene set
 * shows where it first joins.
 */
@Component({
  selector: 'app-dendrogram',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div #chart></div>
    <button type="button" class="p-button p-button-sm p-button-text" (click)="download()">
      Download SVG
    </button>
  `,
})
export class DendrogramComponent implements OnChanges {
  @Input({ required: true }) model!: DendrogramNode;
  @Input() method = '';
  @ViewChild('chart', { static: true }) chart!: ElementRef<HTMLElement>;

  ngOnChanges(): void {
    this.draw();
  }

  download(): void {
    downloadSvg(this.chart.nativeElement, 'jaccard-clustering.svg');
  }

  private draw(): void {
    const host = this.chart.nativeElement;
    const root = hierarchy(this.model);
    const leaves = root.leaves().length;
    const width = 640;
    const height = Math.max(120, leaves * 32) + 50;
    const left = 20;
    const right = 110;
    const svg = freshSvg(
      host,
      width,
      height,
      `Dendrogram of gene sets by Jaccard distance${this.method ? ` (${this.method} linkage)` : ''}`,
    );
    const tooltip = new ChartTooltip(host);

    // `cluster` spaces the leaves evenly; x is then replaced by the merge distance.
    const layout = cluster<DendrogramNode>().size([height - 50, 1])(root);
    // The highest merge anywhere, not the root's: centroid linkage can invert, merging a
    // child above its parent, which a root-only domain would draw outside the plot.
    const maxHeight = Math.max(...root.descendants().map((node) => node.data.height), 1e-9);
    const x = scaleLinear()
      .domain([maxHeight, 0])
      .range([left, width - right]);
    const at = (node: HierarchyPointNode<DendrogramNode>) => ({
      x: x(node.data.height),
      y: node.x + 10,
    });

    const links = svg
      .append('g')
      .attr('fill', 'none')
      .attr('stroke', '#334155')
      .attr('stroke-width', 1.5)
      .selectAll('path')
      .data(layout.links())
      .join('path')
      .attr('d', (link) => {
        const s = at(link.source);
        const t = at(link.target);
        return `M${s.x},${s.y}V${t.y}H${t.x}`;
      });

    const nodes = svg.append('g').selectAll('g').data(layout.descendants()).join('g');
    const leafLabels = nodes
      .filter((n) => !n.children)
      .append('text')
      .attr('x', (n) => at(n).x + 6)
      .attr('y', (n) => at(n).y + 4)
      .text((n) => n.data.name);
    const merges = nodes
      .filter((n) => !!n.children)
      .append('circle')
      .attr('cx', (n) => at(n).x)
      .attr('cy', (n) => at(n).y)
      .attr('r', 5)
      .attr('fill', '#334155');

    svg
      .append('g')
      .attr('transform', `translate(0,${height - 35})`)
      .call(axisBottom(x).ticks(5));
    svg
      .append('text')
      .attr('x', left)
      .attr('y', height - 4)
      .text('Jaccard distance (1 − similarity)');

    // Hovering a merge highlights the cluster it forms: its links and its gene sets.
    interactive(
      merges,
      tooltip,
      (node) => {
        const members = node.leaves().map((leaf) => leaf.data.name);
        return {
          title: `Cluster of ${members.length} gene sets`,
          rows: [
            { label: 'Merged at distance', value: node.data.height.toFixed(3) },
            { label: 'Similarity', value: (1 - node.data.height).toFixed(3) },
            { label: 'Gene sets', value: members.join(', ') },
          ],
          note: `${this.method ? `${this.method[0].toUpperCase()}${this.method.slice(1)}-linkage` : 'Linkage'} distance between the two clusters it joins.`,
        };
      },
      (node) => {
        const inside = new Set(node.descendants());
        links.attr('opacity', (l) => (inside.has(l.target) ? 1 : DIMMED));
        links.attr('stroke', (l) => (inside.has(l.target) ? ACCENT : '#334155'));
        leafLabels.attr('opacity', (n) => (inside.has(n) ? 1 : DIMMED));
        merges.attr('fill', (n) => (n === node ? ACCENT : '#334155'));
      },
      () => {
        links.attr('opacity', 1).attr('stroke', '#334155');
        leafLabels.attr('opacity', 1);
        merges.attr('fill', '#334155');
      },
    );
    interactive(
      leafLabels,
      tooltip,
      (leaf) => {
        const parent = leaf.parent;
        return {
          title: leaf.data.name,
          rows: parent
            ? [
                { label: 'First joins at distance', value: parent.data.height.toFixed(3) },
                {
                  label: 'Joined with',
                  value: parent
                    .leaves()
                    .filter((other) => other !== leaf)
                    .map((other) => other.data.name)
                    .join(', '),
                },
              ]
            : [],
        };
      },
    );
  }
}
