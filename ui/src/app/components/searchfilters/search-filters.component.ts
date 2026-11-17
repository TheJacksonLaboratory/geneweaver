import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputNumberModule } from 'primeng/inputnumber';
import { InputTextModule } from 'primeng/inputtext';
import { MultiSelectModule } from 'primeng/multiselect';

import { InfoTipComponent } from '../infotip/info-tip.component';

import {
  emptyFilters,
  FILTER_HELP,
  filterProblem,
  MAX_GENES,
  parseGenes,
  SCORE_TYPE_OPTIONS,
  SearchFilters,
  SPECIES_OPTIONS,
  TIER_OPTIONS,
} from '../../search/search-filters';

/**
 * Gene set search filters (prototype): any combination of species, tier, score type and size
 * (G3-777), and genes with a score cutoff per score type (G3-764): several at once, all or any
 * (G3-832), and by default their homologs in other species (G3-834).
 *
 * Emits a new `SearchFilters` object on every change, so a holder can compare by reference.
 * Used by the /next search page and the analyze page's gene set picker. Each filter has an
 * info icon whose tooltip says what it does (`FILTER_HELP`).
 */
@Component({
  selector: 'app-search-filters',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ButtonModule,
    InputNumberModule,
    InputTextModule,
    MultiSelectModule,
    InfoTipComponent,
  ],
  template: `
    <div class="search-filters text-left" [attr.id]="idPrefix">
      <div class="formgrid grid">
        <div class="field col-12 md:col-4">
          <div class="flex align-items-center mb-1">
            <label [for]="idPrefix + '-species'" class="text-sm">Species</label>
            <app-info-tip label="Species" [text]="help.species"></app-info-tip>
          </div>
          <p-multiSelect
            [inputId]="idPrefix + '-species'"
            [options]="speciesOptions"
            optionLabel="label"
            optionValue="id"
            [ngModel]="filters.species"
            (ngModelChange)="set('species', $event)"
            placeholder="Any species"
            display="chip"
            [showToggleAll]="false"
            styleClass="w-full"
          ></p-multiSelect>
        </div>
        <div class="field col-12 md:col-4">
          <div class="flex align-items-center mb-1">
            <label [for]="idPrefix + '-tier'" class="text-sm">Curation tier</label>
            <app-info-tip label="Curation tier" [text]="help.tier"></app-info-tip>
          </div>
          <p-multiSelect
            [inputId]="idPrefix + '-tier'"
            [options]="tierOptions"
            optionLabel="label"
            optionValue="id"
            [ngModel]="filters.tiers"
            (ngModelChange)="set('tiers', $event)"
            placeholder="Any tier"
            display="chip"
            [filter]="false"
            [showToggleAll]="false"
            styleClass="w-full"
          ></p-multiSelect>
        </div>
        <div class="field col-12 md:col-4">
          <div class="flex align-items-center mb-1">
            <label [for]="idPrefix + '-score'" class="text-sm">Score type</label>
            <app-info-tip label="Score type" [text]="help.scoreType"></app-info-tip>
          </div>
          <p-multiSelect
            [inputId]="idPrefix + '-score'"
            [options]="scoreTypeOptions"
            optionLabel="label"
            optionValue="id"
            [ngModel]="filters.scoreTypes"
            (ngModelChange)="set('scoreTypes', $event)"
            placeholder="Any score type"
            display="chip"
            [filter]="false"
            [showToggleAll]="false"
            styleClass="w-full"
          ></p-multiSelect>
        </div>
        <div class="field col-6 md:col-2">
          <div class="flex align-items-center mb-1">
            <label [for]="idPrefix + '-min'" class="text-sm">Gene set size, min</label>
            <app-info-tip label="Gene set size, min" [text]="help.sizeMin"></app-info-tip>
          </div>
          <p-inputNumber
            [inputId]="idPrefix + '-min'"
            [ngModel]="filters.sizeMin"
            (ngModelChange)="set('sizeMin', $event)"
            [min]="0"
            [useGrouping]="false"
            styleClass="w-full"
            inputStyleClass="w-full"
          ></p-inputNumber>
        </div>
        <div class="field col-6 md:col-2">
          <div class="flex align-items-center mb-1">
            <label [for]="idPrefix + '-max'" class="text-sm">Gene set size, max</label>
            <app-info-tip label="Gene set size, max" [text]="help.sizeMax"></app-info-tip>
          </div>
          <p-inputNumber
            [inputId]="idPrefix + '-max'"
            [ngModel]="filters.sizeMax"
            (ngModelChange)="set('sizeMax', $event)"
            [min]="0"
            [useGrouping]="false"
            styleClass="w-full"
            inputStyleClass="w-full"
          ></p-inputNumber>
        </div>
        <div class="field col-12 md:col-8">
          <div class="flex align-items-center mb-1">
            <label [for]="idPrefix + '-gene'" class="text-sm">Genes</label>
            <app-info-tip label="Genes" [text]="help.gene"></app-info-tip>
          </div>
          <input
            pInputText
            [id]="idPrefix + '-gene'"
            class="w-full"
            [ngModel]="filters.gene"
            (change)="set('gene', $any($event.target).value)"
            placeholder="e.g. Drd2, or Drd2 AND Tp53, or Drd2 OR Th"
            [attr.aria-describedby]="idPrefix + '-gene-help'"
          />
          <small [id]="idPrefix + '-gene-help'" class="block mt-1 text-color-secondary">
            Finds the gene sets that contain a gene, by any of its identifiers (symbol, Ensembl,
            MGI, ...). Up to {{ maxGenes }} genes: separated by spaces, commas or
            <strong>AND</strong>, a gene set must contain every one; with <strong>OR</strong>
            in capitals, any one. Add score cutoffs below to keep only those where the genes'
            scores are in range, or to list them first.
          </small>
          <div class="flex align-items-center mt-2 text-sm">
            <input
              type="checkbox"
              [id]="idPrefix + '-homology'"
              [ngModel]="filters.homology"
              (ngModelChange)="set('homology', $event)"
              [attr.aria-describedby]="idPrefix + '-homology-help'"
            />
            <label [for]="idPrefix + '-homology'" class="ml-2">Include homologs in other species</label>
            <app-info-tip label="Include homologs in other species" [text]="help.homology"></app-info-tip>
          </div>
          <small [id]="idPrefix + '-homology-help'" class="block mt-1 text-color-secondary">
            So Drd2 also finds zebrafish gene sets holding drd2a, as the analysis tools match
            genes. Clear it to search for the exact gene only.
          </small>
        </div>
      </div>

      <fieldset *ngIf="filters.gene.trim()" class="border-1 surface-border border-round p-3 mb-2">
        <legend class="text-sm px-1">
          Score cutoffs for {{ genesLabel }}
          <app-info-tip label="Score cutoffs" [text]="help.cutoffs"></app-info-tip>
        </legend>
        <div class="formgrid grid">
          <div class="field col-6 md:col-3">
            <div class="flex align-items-center mb-1">
            <label [for]="idPrefix + '-p'" class="text-sm">p-value at most</label>
            <app-info-tip label="p-value at most" [text]="help.pValue"></app-info-tip>
          </div>
            <p-inputNumber [inputId]="idPrefix + '-p'" [ngModel]="filters.pValue" (ngModelChange)="set('pValue', $event)"
              mode="decimal" [minFractionDigits]="0" [maxFractionDigits]="8" [min]="0" [max]="1" placeholder="e.g. 0.05"
              styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
          </div>
          <div class="field col-6 md:col-3">
            <div class="flex align-items-center mb-1">
            <label [for]="idPrefix + '-q'" class="text-sm">q-value at most</label>
            <app-info-tip label="q-value at most" [text]="help.qValue"></app-info-tip>
          </div>
            <p-inputNumber [inputId]="idPrefix + '-q'" [ngModel]="filters.qValue" (ngModelChange)="set('qValue', $event)"
              mode="decimal" [minFractionDigits]="0" [maxFractionDigits]="8" [min]="0" [max]="1" placeholder="e.g. 0.05"
              styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
          </div>
          <div class="field col-6 md:col-3">
            <div class="flex align-items-center mb-1">
            <label [for]="idPrefix + '-corr-low'" class="text-sm">Correlation from / to</label>
            <app-info-tip label="Correlation from / to" [text]="help.correlation"></app-info-tip>
          </div>
            <div class="flex gap-1">
              <p-inputNumber [inputId]="idPrefix + '-corr-low'" [ngModel]="filters.correlationLow"
                (ngModelChange)="set('correlationLow', $event)" mode="decimal" [maxFractionDigits]="6"
                placeholder="from" ariaLabel="Correlation from" styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
              <p-inputNumber [ngModel]="filters.correlationHigh" (ngModelChange)="set('correlationHigh', $event)"
                mode="decimal" [maxFractionDigits]="6" placeholder="to" ariaLabel="Correlation to"
                styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
            </div>
          </div>
          <div class="field col-6 md:col-3">
            <div class="flex align-items-center mb-1">
            <label [for]="idPrefix + '-effect-low'" class="text-sm">Effect from / to</label>
            <app-info-tip label="Effect from / to" [text]="help.effect"></app-info-tip>
          </div>
            <div class="flex gap-1">
              <p-inputNumber [inputId]="idPrefix + '-effect-low'" [ngModel]="filters.effectLow"
                (ngModelChange)="set('effectLow', $event)" mode="decimal" [maxFractionDigits]="6"
                placeholder="from" ariaLabel="Effect from" styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
              <p-inputNumber [ngModel]="filters.effectHigh" (ngModelChange)="set('effectHigh', $event)"
                mode="decimal" [maxFractionDigits]="6" placeholder="to" ariaLabel="Effect to"
                styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
            </div>
          </div>
        </div>
        <div class="flex flex-wrap gap-3 align-items-center text-sm" role="radiogroup" aria-label="Which gene sets to return">
          <div class="flex align-items-center">
            <input type="radio" [id]="idPrefix + '-mode-only'" [name]="idPrefix + '-mode'" value="only"
              [ngModel]="filters.thresholdMode" (ngModelChange)="set('thresholdMode', $event)" />
            <label [for]="idPrefix + '-mode-only'" class="ml-2">{{ onlyLabel }}</label>
            <app-info-tip [label]="onlyLabel" [text]="help.modeOnly"></app-info-tip>
          </div>
          <div class="flex align-items-center">
            <input type="radio" [id]="idPrefix + '-mode-first'" [name]="idPrefix + '-mode'" value="first"
              [ngModel]="filters.thresholdMode" (ngModelChange)="set('thresholdMode', $event)" />
            <label [for]="idPrefix + '-mode-first'" class="ml-2">{{ firstLabel }}</label>
            <app-info-tip [label]="firstLabel" [text]="help.modeFirst"></app-info-tip>
          </div>
        </div>
        <small class="block mt-2 text-color-secondary">
          A gene set has one score type, so each cutoff applies to the gene sets of its type, and
          a gene set passes if its type's cutoff does. With several genes, the cutoff applies to
          each gene's score. Leave a type empty to leave its gene sets out; binary gene sets have
          no score to cut.
        </small>
      </fieldset>

      <div class="flex align-items-center gap-3">
        <small *ngIf="problem" class="search-filters-problem text-orange-600">{{ problem }}</small>
        <p-button label="Clear filters" [text]="true" size="small" icon="pi pi-filter-slash" (onClick)="clear()"></p-button>
      </div>
    </div>
  `,
})
export class SearchFiltersComponent {
  @Input() filters: SearchFilters = emptyFilters();
  @Output() filtersChange = new EventEmitter<SearchFilters>();
  /** Prefix for element ids, so two panels on one page do not collide. */
  @Input() idPrefix = 'filters';

  readonly speciesOptions = SPECIES_OPTIONS;
  readonly tierOptions = TIER_OPTIONS;
  readonly scoreTypeOptions = SCORE_TYPE_OPTIONS;
  readonly maxGenes = MAX_GENES;
  /** The text of each filter's info icon. */
  readonly help = FILTER_HELP;

  /** The genes the cutoffs apply to, as "Drd2, Tp53". */
  get genesLabel(): string {
    return parseGenes(this.filters.gene).genes.join(', ');
  }

  /** The "only" choice, worded for one gene, all of several, or any of several. */
  get onlyLabel(): string {
    const { genes, match } = parseGenes(this.filters.gene);
    if (genes.length < 2) {
      return 'Only gene sets where its score passes';
    }
    return match === 'any'
      ? 'Only gene sets where one of them is held with a passing score'
      : 'Only gene sets where every gene passes';
  }

  /** The "first" choice, worded for one gene or several. */
  get firstLabel(): string {
    return parseGenes(this.filters.gene).genes.length < 2
      ? 'All gene sets holding it, passing ones first'
      : 'All gene sets holding them, those where the most genes pass first';
  }

  get problem(): string | undefined {
    return filterProblem(this.filters);
  }

  /** One field changed: emit a new object, so holders can compare by reference. */
  set(key: keyof SearchFilters, value: unknown): void {
    const next: SearchFilters = { ...this.filters };
    switch (key) {
      case 'gene':
        next.gene = String(value ?? '');
        break;
      case 'species':
      case 'tiers':
      case 'scoreTypes':
        next[key] = Array.isArray(value) ? (value as number[]) : [];
        break;
      case 'homology':
        next.homology = value !== false;
        break;
      case 'thresholdMode':
        next.thresholdMode = value === 'first' ? 'first' : 'only';
        break;
      default:
        next[key] = typeof value === 'number' && Number.isFinite(value) ? value : null;
    }
    this.filters = next;
    this.filtersChange.emit(next);
  }

  clear(): void {
    this.filters = emptyFilters();
    this.filtersChange.emit(this.filters);
  }
}
