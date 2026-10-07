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
import type { Core, ElementDefinition } from 'cytoscape';

import { ACCENT, HIGHLIGHT, saveBlob } from './chart-utils';
import { genesetLabel, phenomeMapElements } from './models';

interface SelectedBiclique {
  genesets: string[];
  genes: string[];
  depth: number;
}

/**
 * PhenomeMap's biclique hierarchy as an interactive graph (Cytoscape.js): one node per
 * biclique -- a maximal group of gene sets sharing a maximal group of genes -- linked to
 * the bicliques it contains, one row per level the tool assigned, from the bicliques
 * spanning the most gene sets at the top. Node size follows the gene count, link width the link score. Clicking a node lists
 * its gene sets and genes.
 *
 * Replaces legacy's Cytoscape Web view, which needed Flash and has not worked in a browser
 * since 2021. Cytoscape is loaded on first use, so no other tool's result pays for it.
 */
@Component({
  selector: 'app-phenome-map-graph',
  standalone: true,
  imports: [NgIf, NgFor],
  template: `
    <div #graph class="graph" role="img" [attr.aria-label]="label"></div>
    <div class="flex gap-2 mt-2">
      <button type="button" class="p-button p-button-sm p-button-text" (click)="fit()">Fit</button>
      <button type="button" class="p-button p-button-sm p-button-text" (click)="downloadPng()">
        Download PNG
      </button>
    </div>
    <p class="text-sm text-color-secondary mt-1">
      Click a node to list its gene sets and genes. Drag to pan, scroll to zoom.
    </p>
    <div *ngIf="selected" class="p-3 surface-100 border-round text-sm">
      <div><strong>Gene sets ({{ selected.genesets.length }}):</strong>
        {{ setLabels(selected.genesets) }}</div>
      <div class="mt-1"><strong>Genes ({{ selected.genes.length }}):</strong>
        {{ selected.genes.join(', ') }}</div>
    </div>
  `,
  styles: ['.graph { height: 520px; border: 1px solid #E2E8F0; border-radius: 6px; }'],
})
export class PhenomeMapGraphComponent implements OnChanges, OnDestroy {
  @Input({ required: true }) result!: Parameters<typeof phenomeMapElements>[0];
  @ViewChild('graph', { static: true }) graph!: ElementRef<HTMLElement>;

  selected?: SelectedBiclique;
  label = 'PhenomeMap biclique graph';
  private cy?: Core;

  constructor(private changes: ChangeDetectorRef) {}

  async ngOnChanges(): Promise<void> {
    const elements = phenomeMapElements(this.result) as ElementDefinition[];
    const nodes = elements.filter((e) => e.group === 'nodes');
    this.label = `PhenomeMap graph of ${nodes.length} bicliques`;
    this.selected = undefined;
    const cytoscape = (await import('cytoscape')).default;
    this.cy?.destroy();
    this.cy = cytoscape({
      container: this.graph.nativeElement,
      elements,
      wheelSensitivity: 0.2,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': ACCENT,
            label: 'data(label)',
            'font-size': 9,
            'text-valign': 'bottom',
            'text-margin-y': 3,
            width: 'mapData(weight, 1, 60, 14, 46)',
            height: 'mapData(weight, 1, 60, 14, 46)',
          },
        },
        { selector: 'node[?emphasize]', style: { 'border-width': 3, 'border-color': HIGHLIGHT } },
        { selector: 'node:selected', style: { 'background-color': '#1E3A8A' } },
        {
          selector: 'edge',
          style: {
            width: 'mapData(score, 0, 1, 1, 6)',
            'line-color': '#94A3B8',
            'target-arrow-color': '#94A3B8',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
          },
        },
      ],
      // Positions come from the tool's own levels (`phenomeMapPositions`), not inferred.
      layout: { name: 'preset', fit: true, padding: 20 },
    });
    this.cy.on('tap', 'node', (event) => {
      const data = event.target.data();
      this.selected = { genesets: data.genesets, genes: data.genes, depth: data.depth };
      this.changes.markForCheck();
    });
  }

  setLabels(ids: string[]): string {
    return ids.map(genesetLabel).join(', ');
  }

  fit(): void {
    this.cy?.fit(undefined, 20);
  }

  downloadPng(): void {
    if (!this.cy) {
      return;
    }
    const blob = this.cy.png({ output: 'blob', full: true, scale: 2, bg: 'white' }) as Blob;
    saveBlob(blob, 'phenome-map.png');
  }

  ngOnDestroy(): void {
    this.cy?.destroy();
  }
}
