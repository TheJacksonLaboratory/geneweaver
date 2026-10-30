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

import { ChartTooltip, saveBlob } from './chart-utils';
import { genesetGraphModel, GenesetGraphModel, GenesetGraphOutput, genesetLabel } from './models';

const setColour = (index: number) => schemeTableau10[index % schemeTableau10.length];

/**
 * GeneSet Graph (legacy GeneSetViewer): gene sets on the left, the genes they hold to the
 * right in columns by degree, each link in its gene set's colour. Emphasised genes are
 * yellow, as legacy drew them. Drawn with Cytoscape, loaded on first use, at the positions
 * `genesetGraphModel` lays out; refused past an edge budget, where the table still lists
 * every gene.
 */
@Component({
  selector: 'app-geneset-graph',
  standalone: true,
  imports: [NgIf, NgFor],
  template: `
    <p class="text-sm text-color-secondary mt-0">{{ model.summary }}</p>
    <p *ngIf="model.tooLarge" class="text-sm text-color-secondary">
      Too many links to draw: more than {{ model.budget }}. Raise the minimum degree, or use the
      table, which lists every gene.
    </p>
    <!-- Always in the DOM, so Cytoscape has its container as soon as the import lands. -->
    <div #graph class="graph" role="img" [attr.aria-label]="label" [hidden]="!drawable"></div>
    <ng-container *ngIf="drawable">
      <ul class="legend list-none p-0 m-0 mt-2 flex flex-wrap gap-3 text-sm">
        <li *ngFor="let item of legend">
          <span class="swatch" [style.background]="item.colour"></span>{{ item.label }}
        </li>
        <li><span class="swatch emphasis"></span>Emphasised gene</li>
      </ul>
      <div class="flex gap-2 mt-2">
        <button type="button" class="p-button p-button-sm p-button-text" (click)="fit()">Fit</button>
        <button type="button" class="p-button p-button-sm p-button-text" (click)="downloadPng()">
          Download PNG
        </button>
      </div>
      <p class="text-sm text-color-secondary mt-1">
        Hover a node for details; click one to light up its links. Drag to pan, scroll to zoom.
      </p>
      <div *ngIf="selectedText" class="p-3 surface-100 border-round text-sm" aria-live="polite">
        {{ selectedText }}
      </div>
    </ng-container>
  `,
  styles: [
    '.graph { height: 560px; border: 1px solid #E2E8F0; border-radius: 6px; }',
    '.swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; }',
    '.swatch.emphasis { background: #FACC15; border-radius: 50%; }',
  ],
})
export class GenesetGraphComponent implements OnChanges, OnDestroy {
  @Input({ required: true }) result!: GenesetGraphOutput;
  @ViewChild('graph', { static: true }) graph!: ElementRef<HTMLElement>;

  model: GenesetGraphModel = genesetGraphModel({
    geneset_ids: [],
    include_homology: false,
    min_degree: 1,
    genesets: [],
    genes: [],
    total_genes: 0,
    min_gene_degree: 0,
    max_gene_degree: 0,
    avg_gene_degree: 0,
  });
  legend: { colour: string; label: string }[] = [];
  label = '';
  selectedText = '';
  private cy?: Core;
  private tooltip?: ChartTooltip;
  private destroyed = false;
  private generation = 0;

  constructor(private changes: ChangeDetectorRef) {}

  get drawable(): boolean {
    return !this.model.tooLarge && this.model.nodes.length > 0;
  }

  async ngOnChanges(): Promise<void> {
    const generation = ++this.generation;
    this.model = genesetGraphModel(this.result);
    this.selectedText = '';
    this.legend = this.result.genesets.map((set, i) => ({
      colour: setColour(i),
      label: genesetLabel(set.id),
    }));
    this.label =
      `GeneSet Graph: ${this.result.genesets.length} gene sets and ${this.result.genes.length} ` +
      `genes held by at least ${this.result.min_degree} of them`;
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
      ...this.model.nodes.map((node) => ({
        group: 'nodes' as const,
        data: {
          id: node.id,
          label: node.label,
          kind: node.kind,
          colour:
            node.kind === 'geneset'
              ? setColour(node.colour ?? 0)
              : node.emphasized
                ? '#FACC15'
                : '#86EFAC',
        },
        position: { x: node.x, y: node.y },
      })),
      ...this.model.edges.map((edge) => ({
        group: 'edges' as const,
        data: { id: edge.id, source: edge.source, target: edge.target, colour: setColour(edge.colour) },
      })),
    ];
    this.cy = cytoscape({
      container: this.graph.nativeElement,
      elements,
      wheelSensitivity: 0.2,
      layout: { name: 'preset', padding: 20 },
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(colour)',
            label: 'data(label)',
            'font-size': 9,
            'text-valign': 'center',
            'text-halign': 'right',
            'text-margin-x': 4,
            width: 12,
            height: 12,
          },
        },
        {
          selector: 'node[kind = "geneset"]',
          style: { shape: 'round-rectangle', width: 18, height: 18, 'text-halign': 'left', 'text-margin-x': -4 },
        },
        { selector: 'node:selected', style: { 'border-width': 3, 'border-color': '#0F172A' } },
        {
          selector: 'edge',
          style: { width: 1, 'line-color': 'data(colour)', opacity: 0.55, 'curve-style': 'bezier' },
        },
        { selector: '.faded', style: { opacity: 0.12 } },
      ],
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
    this.cy.on('tap', (event) => {
      if (event.target === this.cy) {
        this.select('');
      }
    });
  }

  private details(id: string) {
    if (id.startsWith('gs:')) {
      const set = this.result.genesets.find((s) => `gs:${s.id}` === id);
      return {
        title: genesetLabel(set?.id ?? id.slice(3)),
        rows: [
          { label: 'Genes drawn', value: String(set?.genes ?? 0) },
          { label: 'Genes in the run', value: String(set?.size ?? 0) },
        ],
      };
    }
    const gene = this.result.genes.find((g) => `gene:${g.symbol}` === id);
    return {
      title: gene?.symbol ?? id,
      rows: [
        { label: 'In gene sets', value: String(gene?.degree ?? 0) },
        { label: 'Gene sets', value: (gene?.genesets ?? []).map(genesetLabel).join(', ') },
      ],
    };
  }

  /** Light up a node and its links, fading the rest; an empty id clears it. */
  select(id: string): void {
    if (id) {
      const content = this.details(id);
      this.selectedText = [content.title, ...content.rows.map((r) => `${r.label}: ${r.value}`)].join(' · ');
    } else {
      this.selectedText = '';
    }
    if (this.cy) {
      this.cy.elements().removeClass('faded');
      this.cy.$(':selected').unselect();
      if (id) {
        const node = this.cy.getElementById(id);
        node.select();
        this.cy.elements().difference(node.closedNeighborhood()).addClass('faded');
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
    saveBlob(this.cy.png({ output: 'blob', full: true, scale: 2, bg: 'white' }) as Blob, 'geneset-graph.png');
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.cy?.destroy();
  }
}
