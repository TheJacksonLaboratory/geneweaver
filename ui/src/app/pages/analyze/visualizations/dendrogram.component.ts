import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
} from '@angular/core';
import { axisBottom, cluster, hierarchy, HierarchyPointNode, scaleLinear } from 'd3';

import { downloadSvg, freshSvg } from './chart-utils';
import { DendrogramNode } from './models';

/**
 * JaccardClustering's tree, drawn horizontally: leaves (gene sets) on the right, each merge
 * placed at its Jaccard distance on the x axis, so a merge further left joins more
 * dissimilar clusters.
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
    const root = hierarchy(this.model);
    const leaves = root.leaves().length;
    const width = 640;
    const height = Math.max(120, leaves * 32) + 50;
    const left = 20;
    const right = 110;
    const svg = freshSvg(
      this.chart.nativeElement,
      width,
      height,
      `Dendrogram of gene sets by Jaccard distance${this.method ? ` (${this.method} linkage)` : ''}`,
    );

    // `cluster` spaces the leaves evenly; x is then replaced by the merge distance.
    const layout = cluster<DendrogramNode>().size([height - 50, 1])(root);
    const maxHeight = Math.max(this.model.height, 1e-9);
    const x = scaleLinear()
      .domain([maxHeight, 0])
      .range([left, width - right]);
    const at = (node: HierarchyPointNode<DendrogramNode>) => ({
      x: x(node.data.height),
      y: node.x + 10,
    });

    svg
      .append('g')
      .attr('fill', 'none')
      .attr('stroke', '#334155')
      .selectAll('path')
      .data(layout.links())
      .join('path')
      .attr('d', (link) => {
        const s = at(link.source);
        const t = at(link.target);
        return `M${s.x},${s.y}V${t.y}H${t.x}`;
      });

    const nodes = svg.append('g').selectAll('g').data(layout.descendants()).join('g');
    nodes
      .filter((n) => !n.children)
      .append('text')
      .attr('x', (n) => at(n).x + 6)
      .attr('y', (n) => at(n).y + 4)
      .text((n) => n.data.name);
    nodes
      .filter((n) => !!n.children)
      .append('circle')
      .attr('cx', (n) => at(n).x)
      .attr('cy', (n) => at(n).y)
      .attr('r', 3)
      .attr('fill', '#334155')
      .append('title')
      .text((n) => `Merge at Jaccard distance ${n.data.height.toFixed(3)}`);

    svg
      .append('g')
      .attr('transform', `translate(0,${height - 35})`)
      .call(axisBottom(x).ticks(5));
    svg
      .append('text')
      .attr('x', left)
      .attr('y', height - 4)
      .text('Jaccard distance (1 − similarity)');
  }
}
