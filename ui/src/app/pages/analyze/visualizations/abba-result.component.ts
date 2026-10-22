import { NgFor, NgIf } from '@angular/common';
import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import {
  abbaRunInfo,
  AbbaGene,
  AbbaGeneset,
  AbbaResult,
  GENESET_SORTS,
  GenesetSort,
  geneSymbols,
  genesCsv,
  InfoRow,
  occurrenceFraction,
  SparkBar,
  sortGenesets,
  speciesCommonName,
  speciesSparkline,
  speciesTile,
  TileStyle,
  tierBadge,
  tierLabel,
  tierName,
  tierSparkline,
} from './abba-models';
import { AbbaSparklineComponent } from './abba-sparkline.component';
import { saveBlob } from './chart-utils';

/** Seed tiles shown before "Show all": a gene-set seed can expand to a thousand genes. */
const SEED_PREVIEW = 120;

interface GeneRow {
  gene: AbbaGene;
  symbols: string[];
  fraction: number;
  tiers: SparkBar[];
  species: SparkBar[];
  tile: TileStyle;
}

/**
 * ABBA's result, in legacy's four sections: run information, seed genes, the gene sets
 * most connected to the seed, and the genes that recur across those gene sets.
 *
 * Legacy's "Add genes to gene set" posted to an upload page /next does not have; the
 * selected genes can be copied or saved as CSV instead. Selected gene sets can be handed
 * back to the Analyze form, to run another tool over them.
 */
@Component({
  selector: 'app-abba-result',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgFor, NgIf, RouterLink, AbbaSparklineComponent],
  template: `
    <details class="abba-section" open>
      <summary><h4>Run information</h4></summary>
      <dl class="run-info">
        <div *ngFor="let row of info">
          <dt>{{ row.label }}:</dt>
          <dd>{{ row.value }}</dd>
        </div>
      </dl>
    </details>

    <details class="abba-section" open>
      <summary><h4>Seed genes ({{ result.seed_genes.length }})</h4></summary>
      <p class="text-sm text-color-secondary mt-0">
        The genes searched for{{ result.parameters.include_homology ? ', with their homologs' : '' }},
        coloured by species.
      </p>
      <ul class="tiles species-tiles" aria-label="Species in the seed">
        <li
          *ngFor="let species of result.input_species"
          class="tile"
          [style.background]="speciesTile(species).background"
          [style.border-color]="speciesTile(species).border"
          [title]="species"
        >
          {{ species }}
        </li>
      </ul>
      <ul class="tiles gene-tiles" aria-label="Seed genes">
        <li
          *ngFor="let gene of seedTiles"
          class="tile gene-tile"
          [style.background]="speciesTile(gene.species).background"
          [style.border-color]="speciesTile(gene.species).border"
          [title]="gene.symbol + ' (' + (gene.species ?? 'species unknown') + ')'"
        >
          {{ gene.symbol }}<span class="sr-only"> ({{ gene.species ?? 'species unknown' }})</span>
        </li>
      </ul>
      <button
        *ngIf="result.seed_genes.length > seedPreview"
        type="button"
        class="p-button p-button-sm p-button-text"
        (click)="showAllSeeds = !showAllSeeds"
      >
        {{ showAllSeeds ? 'Show fewer' : 'Show all ' + result.seed_genes.length + ' seed genes' }}
      </button>
    </details>

    <details class="abba-section" open>
      <summary><h4>Highly connected gene sets</h4></summary>
      <div class="flex flex-wrap align-items-end justify-content-between gap-2 mb-2">
        <p class="text-sm text-color-secondary m-0">
          Top {{ result.genesets.length }} gene sets of interest: those holding the most seed genes
          ("matches").
        </p>
        <div>
          <label for="abba-sort" class="block text-sm mb-1">Sort results</label>
          <!-- Bound to input, like the options form: see analyze.component.html. -->
          <select
            id="abba-sort"
            class="p-inputtext p-inputtext-sm"
            (input)="sortBy($any($event.target).value)"
          >
            <option *ngFor="let sort of sorts" [value]="sort.value" [selected]="sort.value === sortValue">
              {{ sort.label }}
            </option>
          </select>
        </div>
      </div>
      <div class="overflow-auto">
        <table class="abba-table genesets">
          <thead>
            <tr>
              <th scope="col"><span class="sr-only">Details</span></th>
              <th scope="col">Tier</th>
              <th scope="col">Species</th>
              <th scope="col">Attribution</th>
              <th scope="col">Size</th>
              <th scope="col" class="text-right">Matches</th>
              <th scope="col">Gene set</th>
              <th scope="col"><span class="sr-only">Select</span></th>
            </tr>
          </thead>
          <tbody>
            <ng-container *ngFor="let geneset of genesets; trackBy: trackGeneset">
              <tr>
                <td>
                  <button
                    type="button"
                    class="expander"
                    [attr.aria-expanded]="expanded.has(geneset.gs_id)"
                    [attr.aria-controls]="'abba-gs-' + geneset.gs_id"
                    [attr.aria-label]="'Description of GS' + geneset.gs_id"
                    (click)="toggle(geneset.gs_id)"
                  >
                    {{ expanded.has(geneset.gs_id) ? '−' : '+' }}
                  </button>
                </td>
                <td>
                  <span class="badge" [style.background]="tierBadge(geneset.tier).background"
                    [style.border-color]="tierBadge(geneset.tier).border"
                    [title]="tierName(geneset.tier)">{{ tierLabel(geneset.tier) }}</span>
                </td>
                <td>
                  <span class="badge" [style.background]="speciesTile(speciesName(geneset.species_id)).background"
                    [style.border-color]="speciesTile(speciesName(geneset.species_id)).border"
                    [title]="speciesName(geneset.species_id)">{{ speciesCommonName(speciesName(geneset.species_id)) }}</span>
                </td>
                <td>
                  <span *ngIf="geneset.attribution" class="badge attribution">{{ geneset.attribution }}</span>
                </td>
                <td><span class="badge size">{{ geneset.gene_count.toLocaleString() }} genes</span></td>
                <td class="text-right"><strong>{{ geneset.matches }}</strong></td>
                <td class="title">
                  <a [routerLink]="['/geneset', geneset.gs_id]"><strong>GS{{ geneset.gs_id }}</strong> ▸ {{ geneset.name }}</a>
                </td>
                <td>
                  <input
                    type="checkbox"
                    [checked]="selectedGenesets.has(geneset.gs_id)"
                    [attr.aria-label]="'Select GS' + geneset.gs_id"
                    (change)="toggleGeneset(geneset.gs_id)"
                  />
                </td>
              </tr>
              <tr *ngIf="expanded.has(geneset.gs_id)" [id]="'abba-gs-' + geneset.gs_id" class="description">
                <td></td>
                <td colspan="7">
                  <div *ngIf="geneset.abbreviation"><strong>{{ geneset.abbreviation }}</strong></div>
                  {{ geneset.description || 'No description.' }}
                </td>
              </tr>
            </ng-container>
            <tr *ngIf="!genesets.length">
              <td colspan="8">No gene set holds enough of the seed genes. Try fewer minimum genes or more tiers.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <button
        type="button"
        class="p-button p-button-sm p-button-outlined mt-2"
        [disabled]="!selectedGenesets.size"
        (click)="useGenesets.emit(selectedGenesetIds)"
      >
        Use {{ selectedGenesets.size || '' }} selected gene set{{ selectedGenesets.size === 1 ? '' : 's' }} in the Analyze form
      </button>
    </details>

    <details class="abba-section" open>
      <summary><h4>Genes of interest</h4></summary>
      <div class="flex flex-wrap align-items-end justify-content-between gap-2 mb-2">
        <p class="text-sm text-color-secondary m-0">
          Top {{ result.genes.length }} genes, not in the seed, that occur in the most of those gene
          sets.
        </p>
        <div class="flex gap-2">
          <button type="button" class="p-button p-button-sm" [disabled]="!selectedGenes.size" (click)="copyGenes()">
            Copy selected genes
          </button>
          <button type="button" class="p-button p-button-sm p-button-outlined" [disabled]="!selectedGenes.size" (click)="downloadGenes()">
            Download CSV
          </button>
        </div>
      </div>
      <p class="sr-only" aria-live="polite">{{ status }}</p>
      <p *ngIf="status" class="text-sm mt-0" aria-hidden="true">{{ status }}</p>
      <div class="overflow-auto">
        <table class="abba-table genes">
          <thead>
            <tr>
              <th scope="col">Gene symbol</th>
              <th scope="col">Species</th>
              <th scope="col">Represented gene sets</th>
              <th scope="col">Gene sets by curation tier</th>
              <th scope="col">Gene sets by species</th>
              <th scope="col">
                <input
                  type="checkbox"
                  class="select-all"
                  aria-label="Select all genes"
                  [checked]="allGenesSelected"
                  [indeterminate]="selectedGenes.size > 0 && !allGenesSelected"
                  (change)="toggleAllGenes()"
                />
              </th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let row of geneRows; trackBy: trackGene">
              <td class="symbols">
                <strong>{{ row.symbols[0] }}</strong>
                <span *ngIf="row.symbols.length > 1" class="text-color-secondary"> {{ row.symbols.slice(1).join(' ') }}</span>
              </td>
              <td>
                <span class="badge" [style.background]="row.tile.background" [style.border-color]="row.tile.border"
                  [title]="row.gene.species">{{ speciesCommonName(row.gene.species) }}</span>
              </td>
              <td>
                <div
                  class="meter"
                  role="meter"
                  aria-valuemin="0"
                  [attr.aria-valuemax]="result.max_occurrences"
                  [attr.aria-valuenow]="row.gene.occurrences"
                  [attr.aria-label]="row.gene.symbol + ' is in ' + row.gene.occurrences + ' of the gene sets'"
                >
                  <div class="meter-fill" [style.width.%]="row.fraction * 100"></div>
                  <span class="meter-text">{{ row.gene.occurrences.toLocaleString() }}</span>
                </div>
              </td>
              <td><app-abba-sparkline [bars]="row.tiers" [title]="row.gene.symbol + ': gene sets by curation tier'"></app-abba-sparkline></td>
              <td><app-abba-sparkline [bars]="row.species" [title]="row.gene.symbol + ': gene sets by species (log scale)'"></app-abba-sparkline></td>
              <td>
                <input
                  type="checkbox"
                  [checked]="selectedGenes.has(row.gene.ode_gene_id)"
                  [attr.aria-label]="'Select ' + row.gene.symbol"
                  (change)="toggleGene(row.gene.ode_gene_id)"
                />
              </td>
            </tr>
            <tr *ngIf="!geneRows.length">
              <td colspan="6">No gene recurs across the matching gene sets.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  `,
  styles: [
    `
      .abba-section { margin-bottom: 1.25rem; }
      .abba-section > summary { cursor: pointer; list-style-position: outside; }
      .abba-section > summary h4 { display: inline; margin: 0; }
      .run-info { display: grid; grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr)); gap: 0.25rem 2rem; margin: 0.75rem 0 0; }
      .run-info div { display: flex; gap: 0.4rem; }
      .run-info dt { font-weight: 600; }
      .run-info dd { margin: 0; }
      .tiles { list-style: none; padding: 0; margin: 0.75rem 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr)); gap: 0.6rem; }
      .tile { border: 1px solid; border-radius: 3px; padding: 0.35rem 0.6rem; color: #1f2937; font-weight: 600;
              white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .gene-tile { font-size: 1.1rem; padding: 0.6rem; }
      .abba-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
      .abba-table th { text-align: left; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.02em;
                       border-bottom: 3px solid #006644; padding: 0.5rem; }
      .abba-table td { border-bottom: 1px solid var(--surface-border, #e5e7eb); padding: 0.45rem 0.5rem; vertical-align: middle; }
      .abba-table .text-right { text-align: right; }
      .abba-table .title { min-width: 18rem; }
      .abba-table .symbols { min-width: 12rem; }
      .description td { background: var(--surface-50, #f8fafc); }
      .badge { display: inline-block; border: 1px solid; padding: 1px 6px; font-size: 0.7rem; font-weight: 700;
               color: #111827; white-space: nowrap; border-radius: 2px; }
      .badge.size { background: transparent; border-color: #5cb85c; color: inherit; }
      .badge.attribution { background: #e0f2fe; border-color: #7dd3fc; }
      .expander { width: 1.6rem; height: 1.6rem; border: 1px solid var(--surface-border, #cbd5e1); background: transparent;
                  color: inherit; font-weight: 700; cursor: pointer; border-radius: 3px; }
      .meter { position: relative; min-width: 12rem; height: 1.3rem; background: var(--surface-200, #e5e7eb); border-radius: 3px; overflow: hidden; }
      .meter-fill { height: 100%; background: #5cb85c; }
      .meter-text { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
                    font-size: 0.75rem; font-weight: 600; color: #0f172a; }
      .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); border: 0; }
    `,
  ],
})
export class AbbaResultComponent implements OnChanges {
  @Input({ required: true }) result!: AbbaResult;
  /** When the result arrived; legacy's "Date". */
  @Input() ranAt?: Date;
  /** The gene sets the user chose to hand back to the Analyze form. */
  @Output() useGenesets = new EventEmitter<number[]>();

  readonly sorts = GENESET_SORTS;
  readonly seedPreview = SEED_PREVIEW;
  readonly speciesTile = speciesTile;
  readonly speciesCommonName = speciesCommonName;
  readonly tierBadge = tierBadge;

  info: InfoRow[] = [];
  genesets: AbbaGeneset[] = [];
  geneRows: GeneRow[] = [];
  sortValue: GenesetSort = 'none';
  showAllSeeds = false;
  expanded = new Set<number>();
  selectedGenesets = new Set<number>();
  selectedGenes = new Set<number>();
  status = '';

  constructor(private changes: ChangeDetectorRef) {}

  ngOnChanges(): void {
    const r = this.result;
    this.info = abbaRunInfo(r, this.ranAt);
    this.sortValue = 'none';
    this.genesets = sortGenesets(r.genesets ?? [], 'none');
    this.geneRows = (r.genes ?? []).map((gene) => ({
      gene,
      symbols: geneSymbols(gene),
      fraction: occurrenceFraction(gene, r.max_occurrences),
      tiers: tierSparkline(gene, r.tiers),
      species: speciesSparkline(gene, r.species ?? {}),
      tile: speciesTile(gene.species),
    }));
    this.expanded.clear();
    this.selectedGenesets.clear();
    this.selectedGenes.clear();
    this.showAllSeeds = false;
    this.status = '';
  }

  get seedTiles() {
    const seeds = this.result.seed_genes ?? [];
    return this.showAllSeeds ? seeds : seeds.slice(0, SEED_PREVIEW);
  }

  tierLabel(tier: number | null): string {
    return tierLabel(tier, this.result.tiers);
  }

  tierName(tier: number | null): string {
    return tierName(tier, this.result.tiers);
  }

  speciesName(id: number | null): string {
    return id === null ? '' : (this.result.species?.[String(id)] ?? `Species ${id}`);
  }

  sortBy(value: string): void {
    const sort = GENESET_SORTS.find((option) => option.value === value)?.value;
    if (!sort) {
      return; // An empty event (e.g. as options render) is not a choice.
    }
    this.sortValue = sort;
    this.genesets = sortGenesets(this.result.genesets ?? [], sort, this.result.species);
  }

  toggle(gsId: number): void {
    if (!this.expanded.delete(gsId)) {
      this.expanded.add(gsId);
    }
  }

  toggleGeneset(gsId: number): void {
    if (!this.selectedGenesets.delete(gsId)) {
      this.selectedGenesets.add(gsId);
    }
  }

  get selectedGenesetIds(): number[] {
    // In the table's order, not the order clicked.
    return this.genesets.map((g) => g.gs_id).filter((id) => this.selectedGenesets.has(id));
  }

  toggleGene(odeGeneId: number): void {
    if (!this.selectedGenes.delete(odeGeneId)) {
      this.selectedGenes.add(odeGeneId);
    }
  }

  get allGenesSelected(): boolean {
    return this.geneRows.length > 0 && this.selectedGenes.size === this.geneRows.length;
  }

  toggleAllGenes(): void {
    if (this.allGenesSelected) {
      this.selectedGenes.clear();
    } else {
      this.geneRows.forEach((row) => this.selectedGenes.add(row.gene.ode_gene_id));
    }
  }

  private get chosenGenes(): AbbaGene[] {
    return this.geneRows.map((row) => row.gene).filter((gene) => this.selectedGenes.has(gene.ode_gene_id));
  }

  copyGenes(): void {
    const genes = this.chosenGenes;
    const text = genes.map((gene) => gene.symbol).join('\n');
    const done = (message: string) => {
      this.status = message;
      this.changes.markForCheck();
    };
    if (!navigator.clipboard) {
      done('Copying is not available in this browser; use Download CSV.');
      return;
    }
    navigator.clipboard.writeText(text).then(
      () => done(`Copied ${genes.length} gene${genes.length === 1 ? '' : 's'}.`),
      () => done('Could not copy; use Download CSV.'),
    );
  }

  downloadGenes(): void {
    const genes = this.chosenGenes;
    saveBlob(new Blob([genesCsv(genes)], { type: 'text/csv' }), 'abba-genes.csv');
    this.status = `Saved ${genes.length} gene${genes.length === 1 ? '' : 's'} as abba-genes.csv.`;
  }

  trackGeneset(_index: number, geneset: AbbaGeneset): number {
    return geneset.gs_id;
  }

  trackGene(_index: number, row: GeneRow): number {
    return row.gene.ode_gene_id;
  }
}
