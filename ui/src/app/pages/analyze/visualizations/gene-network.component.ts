import { NgFor, NgIf } from '@angular/common';
import {
  ChangeDetectorRef,
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  ViewChild,
} from '@angular/core';
import { schemeTableau10 } from 'd3';
import type { Core, ElementDefinition } from 'cytoscape';

import { ChartTooltip, MUTED, saveBlob } from './chart-utils';
import { dbscanNetwork, GeneNetwork, genesetLabel } from './models';

const clusterColour = (cluster: number | null) =>
  cluster === null ? MUTED : schemeTableau10[cluster % schemeTableau10.length];

/**
 * DBSCAN as legacy's "wires" view: genes linked when they share an input gene set, coloured
 * by cluster, unclustered genes (noise) in grey. Drawn with Cytoscape, loaded on first use.
 * Refused past an edge budget, as legacy refused: a few large gene sets link every pair of
 * their genes, and thousands of links draw as a solid mass.
 */
@Component({
  selector: 'app-gene-network',
  standalone: true,
  imports: [NgIf, NgFor],
  template: `
    <p *ngIf="!network.available" class="text-sm text-color-secondary">
      The network view needs each gene's gene sets, which this result does not carry. Results
      from an updated tools worker include them.
    </p>
    <p *ngIf="network.tooLarge" class="text-sm text-color-secondary">
      Too many links to draw: these gene sets link more than {{ network.budget }} pairs of genes,
      which would draw as a solid mass. The circles view shows the clusters; a network is
      drawn for smaller gene sets.
    </p>
    <!-- Always in the DOM, so Cytoscape has its container as soon as the import lands. -->
    <div #graph class="graph" role="img" [attr.aria-label]="label" [hidden]="!drawable"></div>
    <ng-container *ngIf="drawable">
      <ul class="legend list-none p-0 m-0 mt-2 flex flex-wrap gap-3 text-sm">
        <li *ngFor="let item of legend">
          <span class="swatch" [style.background]="item.colour"></span>{{ item.label }}
        </li>
      </ul>
      <div class="flex gap-2 mt-2">
        <button type="button" class="p-button p-button-sm p-button-text" (click)="fit()">Fit</button>
        <button type="button" class="p-button p-button-sm p-button-text" (click)="downloadPng()">
          Download PNG
        </button>
      </div>
      <p class="text-sm text-color-secondary mt-1">
        Hover a gene for its cluster and gene sets, or choose one below. Drag to pan, scroll to
        zoom.
      </p>
      <label class="block text-sm mb-1" for="network-gene-picker">Gene</label>
      <select
        id="network-gene-picker"
        class="p-inputtext p-inputtext-sm mb-2 w-full"
        [value]="selectedId ?? ''"
        (change)="select($any($event.target).value)"
      >
        <option value="">Choose a gene…</option>
        <option *ngFor="let node of network.nodes" [value]="node.id">{{ node.id }}</option>
      </select>
      <div *ngIf="selectedText" class="p-3 surface-100 border-round text-sm" aria-live="polite">
        {{ selectedText }}
      </div>
    </ng-container>
  `,
  styles: [
    '.graph { height: 480px; border: 1px solid #E2E8F0; border-radius: 6px; }',
    '.swatch { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }',
  ],
})
export class GeneNetworkComponent implements OnChanges, OnDestroy {
  @Input({ required: true }) result!: Parameters<typeof dbscanNetwork>[0];
  @ViewChild('graph', { static: true }) graph!: ElementRef<HTMLElement>;

  network: GeneNetwork = dbscanNetwork({ ran: false, clusters: [] });
  legend: { colour: string; label: string }[] = [];
  label = '';
  selectedId?: string;
  selectedText = '';
  private cy?: Core;
  private tooltip?: ChartTooltip;
  private destroyed = false;
  private generation = 0;

  constructor(private changes: ChangeDetectorRef) {}

  get drawable(): boolean {
    return this.network.available && !this.network.tooLarge && this.network.nodes.length > 0;
  }

  async ngOnChanges(): Promise<void> {
    const generation = ++this.generation;
    this.network = dbscanNetwork(this.result);
    this.selectedId = undefined;
    this.selectedText = '';
    const noise = this.network.nodes.some((node) => node.cluster === null);
    this.legend = [
      ...Array.from({ length: this.network.clusters }, (_, i) => ({
        colour: clusterColour(i),
        label: `Cluster ${i + 1}`,
      })),
      ...(noise ? [{ colour: clusterColour(null), label: 'Noise (no cluster)' }] : []),
    ];
    this.label = `Network of ${this.network.nodes.length} genes and ${this.network.edges.length} links`;
    this.cy?.destroy();
    this.cy = undefined;
    if (!this.drawable) {
      return;
    }
    const cytoscape = (await import('cytoscape')).default;
    if (this.destroyed || generation !== this.generation) {
      return;
    }
    const elements: ElementDefinition[] = [
      ...this.network.nodes.map((node) => ({
        group: 'nodes' as const,
        data: { id: node.id, colour: clusterColour(node.cluster) },
      })),
      ...this.network.edges.map((edge, i) => ({
        group: 'edges' as const,
        data: { id: `e${i}`, source: edge.source, target: edge.target, weight: edge.genesets.length },
      })),
    ];
    const reduceMotion =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.cy = cytoscape({
      container: this.graph.nativeElement,
      elements,
      wheelSensitivity: 0.2,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(colour)',
            label: 'data(id)',
            'font-size': 8,
            width: 14,
            height: 14,
          },
        },
        { selector: 'node:selected', style: { 'border-width': 3, 'border-color': '#0F172A' } },
        {
          selector: 'edge',
          style: { width: 'mapData(weight, 1, 5, 0.5, 3)', 'line-color': '#CBD5E1', 'curve-style': 'haystack' },
        },
      ],
      layout: { name: 'cose', animate: !reduceMotion, padding: 20 },
    });
    // One tooltip per component, not per result: the host keeps it across redraws.
    this.tooltip ??= new ChartTooltip(this.graph.nativeElement.parentElement ?? this.graph.nativeElement);
    this.cy.on('mouseover', 'node', (event) => {
      const original = event.originalEvent as MouseEvent | undefined;
      if (original) {
        this.tooltip?.show(this.details(String(event.target.id())), original);
      }
    });
    this.cy.on('mouseout', 'node', () => this.tooltip?.hide());
    this.cy.on('tap', 'node', (event) => this.select(String(event.target.id())));
  }

  private details(id: string) {
    const node = this.network.nodes.find((n) => n.id === id);
    return {
      title: id,
      rows: [
        { label: 'Cluster', value: node?.cluster === null || !node ? 'none (noise)' : String(node.cluster + 1) },
        { label: 'Gene sets', value: (node?.genesets ?? []).map(genesetLabel).join(', ') },
        {
          label: 'Linked genes',
          value: String(this.network.edges.filter((e) => e.source === id || e.target === id).length),
        },
      ],
    };
  }

  /** One selection path for a click on the graph and for the picker. */
  select(id: string): void {
    this.selectedId = id || undefined;
    if (id) {
      const content = this.details(id);
      this.selectedText = [content.title, ...content.rows.map((r) => `${r.label}: ${r.value}`)].join(' · ');
    } else {
      this.selectedText = '';
    }
    if (this.cy) {
      this.cy.$(':selected').unselect();
      if (id) {
        this.cy.getElementById(id).select();
      }
    }
    this.changes.markForCheck();
  }

  fit(): void {
    this.cy?.fit(undefined, 20);
  }

  downloadPng(): void {
    if (!this.cy) {
      return;
    }
    saveBlob(this.cy.png({ output: 'blob', full: true, scale: 2, bg: 'white' }) as Blob, 'dbscan-network.png');
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.cy?.destroy();
  }
}
