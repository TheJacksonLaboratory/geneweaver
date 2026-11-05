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
import {
  genesetLabel,
  phenomeMapElements,
  phenomeMapMatches,
  phenomeMapStats,
  TooltipRow,
} from './models';

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
    <dl class="stats flex flex-wrap gap-3 text-sm m-0 mb-2">
      <div *ngFor="let stat of stats"><dt class="inline font-semibold">{{ stat.label }}:</dt>
        <dd class="inline m-0 ml-1">{{ stat.value }}</dd></div>
    </dl>
    <label class="block text-sm mb-1" for="phenome-map-search">Highlight genes or gene sets</label>
    <input
      id="phenome-map-search"
      class="p-inputtext p-inputtext-sm mb-1 w-full"
      type="search"
      placeholder="e.g. Drd2, GS164706"
      [value]="query"
      (input)="highlight($any($event.target).value)"
    />
    <p class="text-sm text-color-secondary mt-0 mb-2" aria-live="polite">{{ matchNote }}</p>
    <!-- The canvas is a picture for sighted users; the list below is the accessible way in. -->
    <div #graph class="graph" role="img" [attr.aria-label]="label"></div>
    <div class="flex gap-2 mt-2">
      <button type="button" class="p-button p-button-sm p-button-text" (click)="fit()">Fit</button>
      <button type="button" class="p-button p-button-sm p-button-text" (click)="downloadPng()">
        Download PNG
      </button>
    </div>
    <p class="text-sm text-color-secondary mt-1">
      Click a node, or choose a biclique below, to list its gene sets and genes. Drag to pan,
      scroll to zoom.
    </p>
    <label class="block text-sm mb-1" for="biclique-picker">Biclique</label>
    <select
      id="biclique-picker"
      class="p-inputtext p-inputtext-sm mb-2 w-full"
      [value]="selectedId ?? ''"
      (change)="select($any($event.target).value)"
    >
      <option value="">Choose a biclique…</option>
      <option *ngFor="let option of options" [value]="option.id">{{ option.label }}</option>
    </select>
    <div *ngIf="selected" class="p-3 surface-100 border-round text-sm" aria-live="polite">
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
  selectedId?: string;
  /** Every displayed biclique, top level first, for the keyboard-operable picker. */
  options: { id: string; label: string }[] = [];
  label = 'PhenomeMap biclique graph';
  stats: TooltipRow[] = [];
  query = '';
  matchNote = '';
  private matches = new Set<string>();
  private cy?: Core;
  private details = new Map<string, SelectedBiclique>();
  private destroyed = false;
  /** Bumped per change, so a slow import for an older result does not draw over a newer one. */
  private generation = 0;

  constructor(private changes: ChangeDetectorRef) {}

  async ngOnChanges(): Promise<void> {
    const generation = ++this.generation;
    const elements = phenomeMapElements(this.result) as ElementDefinition[];
    const nodes = elements.filter((e) => e.group === 'nodes');
    this.label = `PhenomeMap graph of ${nodes.length} bicliques`;
    this.stats = phenomeMapStats(this.result);
    this.selected = undefined;
    this.selectedId = undefined;
    this.query = '';
    this.matchNote = '';
    this.matches.clear();
    this.details = new Map(
      nodes.map((node) => [
        String(node.data.id),
        {
          genesets: node.data['genesets'] as string[],
          genes: node.data['genes'] as string[],
          depth: node.data['depth'] as number,
        },
      ]),
    );
    this.options = nodes
      .map((node) => {
        const genesets = node.data['genesets'] as string[];
        return {
          id: String(node.data.id),
          depth: node.data['depth'] as number,
          label: `Level ${node.data['depth']}: ${node.data['label']} (${this.setLabels(genesets)})`,
        };
      })
      .sort((a, b) => a.depth - b.depth)
      .map(({ id, label }) => ({ id, label }));

    const cytoscape = (await import('cytoscape')).default;
    // The import is async: the component may have been destroyed, or handed a newer result,
    // while it loaded. Creating an instance then would leak it (nothing would destroy it) or
    // draw a stale graph.
    if (this.destroyed || generation !== this.generation) {
      return;
    }
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
        { selector: 'node.matched', style: { 'border-width': 4, 'border-color': '#F59E0B' } },
        { selector: '.dimmed', style: { opacity: 0.15 } },
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
    this.cy.on('tap', 'node', (event) => this.select(String(event.target.id())));
    this.applyHighlight();
  }

  /** Legacy's search box: mark the bicliques holding a match, fade the rest. */
  highlight(query: string): void {
    this.query = query;
    const ids = phenomeMapMatches(this.result.nodes, query);
    this.matches = new Set([...ids].map((id) => `n${id}`));
    const shown = this.options.length;
    this.matchNote = query.trim()
      ? `${ids.size} of ${shown} bicliques contain a match.`
      : '';
    this.applyHighlight();
    this.changes.markForCheck();
  }

  private applyHighlight(): void {
    const cy = this.cy;
    if (!cy) {
      return;
    }
    const active = this.query.trim() !== '';
    cy.batch(() => {
      cy.elements().removeClass('dimmed matched');
      if (!active) {
        return;
      }
      cy.nodes().forEach((node) => {
        node.addClass(this.matches.has(node.id()) ? 'matched' : 'dimmed');
      });
      // A link stays lit only between two matches: the paths legacy highlighted.
      cy.edges().forEach((edge) => {
        if (!(this.matches.has(edge.source().id()) && this.matches.has(edge.target().id()))) {
          edge.addClass('dimmed');
        }
      });
    });
  }

  /** One selection path for both a click on the graph and the picker. */
  select(id: string): void {
    this.selectedId = id || undefined;
    this.selected = id ? this.details.get(id) : undefined;
    if (this.cy) {
      this.cy.$(':selected').unselect();
      if (id) {
        this.cy.getElementById(id).select();
      }
    }
    this.changes.markForCheck();
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
    this.destroyed = true;
    this.cy?.destroy();
  }
}
