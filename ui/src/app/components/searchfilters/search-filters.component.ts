import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputNumberModule } from 'primeng/inputnumber';
import { InputTextModule } from 'primeng/inputtext';
import { MultiSelectModule } from 'primeng/multiselect';

import {
  emptyFilters,
  filterProblem,
  SCORE_TYPE_OPTIONS,
  SearchFilters,
  SPECIES_OPTIONS,
  TIER_OPTIONS,
} from '../../search/search-filters';

/**
 * Gene set search filters (prototype): any combination of species, tier, score type and size
 * (G3-777), and a gene with a score cutoff per score type (G3-764).
 *
 * Emits a new `SearchFilters` object on every change, so a holder can compare by reference.
 * Used by the /next search page and the analyze page's gene set picker.
 */
@Component({
  selector: 'app-search-filters',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonModule, InputNumberModule, InputTextModule, MultiSelectModule],
  template: `
    <div class="search-filters text-left" [attr.id]="idPrefix">
      <div class="formgrid grid">
        <div class="field col-12 md:col-4">
          <label [for]="idPrefix + '-species'" class="block mb-1 text-sm">Species</label>
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
          <label [for]="idPrefix + '-tier'" class="block mb-1 text-sm">Curation tier</label>
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
          <label [for]="idPrefix + '-score'" class="block mb-1 text-sm">Score type</label>
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
          <label [for]="idPrefix + '-min'" class="block mb-1 text-sm">Gene set size, min</label>
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
          <label [for]="idPrefix + '-max'" class="block mb-1 text-sm">Gene set size, max</label>
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
          <label [for]="idPrefix + '-gene'" class="block mb-1 text-sm">Gene</label>
          <input
            pInputText
            [id]="idPrefix + '-gene'"
            class="w-full"
            [ngModel]="filters.gene"
            (change)="set('gene', $any($event.target).value)"
            placeholder="e.g. Drd2, ENSMUSG00000032259, MGI:94924"
            [attr.aria-describedby]="idPrefix + '-gene-help'"
          />
          <small [id]="idPrefix + '-gene-help'" class="block mt-1 text-color-secondary">
            Finds the gene sets that contain this gene, by any of its identifiers. Add score
            cutoffs below to keep only those where its score is in range, or to list them first.
          </small>
        </div>
      </div>

      <fieldset *ngIf="filters.gene.trim()" class="border-1 surface-border border-round p-3 mb-2">
        <legend class="text-sm px-1">Score cutoffs for {{ filters.gene.trim() }}</legend>
        <div class="formgrid grid">
          <div class="field col-6 md:col-3">
            <label [for]="idPrefix + '-p'" class="block mb-1 text-sm">p-value at most</label>
            <p-inputNumber [inputId]="idPrefix + '-p'" [ngModel]="filters.pValue" (ngModelChange)="set('pValue', $event)"
              mode="decimal" [minFractionDigits]="0" [maxFractionDigits]="8" [min]="0" [max]="1" placeholder="e.g. 0.05"
              styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
          </div>
          <div class="field col-6 md:col-3">
            <label [for]="idPrefix + '-q'" class="block mb-1 text-sm">q-value at most</label>
            <p-inputNumber [inputId]="idPrefix + '-q'" [ngModel]="filters.qValue" (ngModelChange)="set('qValue', $event)"
              mode="decimal" [minFractionDigits]="0" [maxFractionDigits]="8" [min]="0" [max]="1" placeholder="e.g. 0.05"
              styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
          </div>
          <div class="field col-6 md:col-3">
            <label [for]="idPrefix + '-corr-low'" class="block mb-1 text-sm">Correlation from / to</label>
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
            <label [for]="idPrefix + '-effect-low'" class="block mb-1 text-sm">Effect from / to</label>
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
            <label [for]="idPrefix + '-mode-only'" class="ml-2">Only gene sets where its score passes</label>
          </div>
          <div class="flex align-items-center">
            <input type="radio" [id]="idPrefix + '-mode-first'" [name]="idPrefix + '-mode'" value="first"
              [ngModel]="filters.thresholdMode" (ngModelChange)="set('thresholdMode', $event)" />
            <label [for]="idPrefix + '-mode-first'" class="ml-2">All gene sets holding it, passing ones first</label>
          </div>
        </div>
        <small class="block mt-2 text-color-secondary">
          A gene set has one score type, so each cutoff applies to the gene sets of its type, and
          a gene set passes if its type's cutoff does. Leave a type empty to leave its gene sets
          out; binary gene sets have no score to cut.
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
