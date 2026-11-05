import { Component, EventEmitter, OnDestroy, OnInit, Output, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { ApiBaseService, ApiBaseServiceFactory, Paging } from 'jax-apiutils';
import { Subscription, take } from 'rxjs';
import { AutoComplete, AutoCompleteModule } from 'primeng/autocomplete';
import { ButtonModule } from 'primeng/button';
import { ProgressBarModule } from 'primeng/progressbar';

import { environment } from '../../../environments/environment';
import { GeneSet } from '../../models/gene-set';
import { GenesetOption, PAGE_SIZE } from '../../search/geneset-options';
import { GenesetSearchSource } from '../../search/geneset-search-source';
import {
  activeFilterCount,
  canSearch,
  describeSearch,
  emptyFilters,
  filterProblem,
  fromQueryParams,
  searchParams,
  SearchFilters,
  Sort,
  toQueryParams,
} from '../../search/search-filters';
import { LIST_HEIGHT, ROW_HEIGHT_PX, SUGGESTION_STYLES } from '../../search/suggestion-list';
import { SearchFiltersComponent } from '../searchfilters/search-filters.component';

/**
 * The /next search field: the analyze page's autocomplete, for finding gene sets.
 *
 * - Typing lists matching gene sets, a page at a time as the list scrolls; choosing one opens it.
 * - Enter or Search runs the full search and emits its results, as the previous search bar
 *   did (`components/searchbar`, kept for reference). The URL holds the search, its filters
 *   and its sort, so a search can be shared and survives a reload.
 * - Filters (G3-777) and a gene with score cutoffs (G3-764) narrow both the suggestions and
 *   the results. A gene alone is a search: text is optional when one is given.
 * - `sortBy`, `changePage` and the paging fields are for the results table and paginator
 *   below it: results come a page at a time, and the API counts every match for the total.
 */
@Component({
  selector: 'app-geneset-search',
  standalone: true,
  imports: [CommonModule, FormsModule, AutoCompleteModule, ButtonModule, ProgressBarModule, SearchFiltersComponent],
  styles: [SUGGESTION_STYLES],
  template: `
    <div class="flex gap-2 align-items-start">
      <div class="flex-1 min-w-0">
        <p-autoComplete
          inputId="genesetSearch"
          [(ngModel)]="text"
          [suggestions]="source.suggestions"
          (completeMethod)="source.search($event.query)"
          optionLabel="chip"
          [delay]="300"
          [minLength]="2"
          [virtualScroll]="true"
          [virtualScrollItemSize]="rowHeight"
          [lazy]="true"
          (onLazyLoad)="source.loadMore($event.last)"
          [scrollHeight]="listHeight"
          [showEmptyMessage]="true"
          emptyMessage="No gene sets match. Press Enter to search anyway, or change the filters."
          (onSelect)="open($event.value)"
          (onKeyUp)="keyUp($event)"
          placeholder="Search gene sets by keyword or ID"
          ariaLabel="Search gene sets"
          styleClass="w-full"
          inputStyleClass="w-full"
        >
          <ng-template let-option pTemplate="item">
            <div class="geneset-option text-left" [attr.data-gs-id]="option.id">
              <div class="white-space-nowrap overflow-hidden text-overflow-ellipsis font-normal">
                <strong>GS{{ option.id }}</strong>
                <span *ngIf="option.abbreviation" class="ml-2">{{ option.abbreviation }}</span>
              </div>
              <small *ngIf="option.detail" class="block text-color-secondary font-normal">{{ option.detail }}</small>
            </div>
          </ng-template>
        </p-autoComplete>
      </div>
      <p-button label="Search" styleClass="p-button-success search-button" [disabled]="!searchable" (onClick)="submit()"></p-button>
      <p-button
        [label]="filterCount ? 'Filters (' + filterCount + ')' : 'Filters'"
        icon="pi pi-filter"
        [outlined]="true"
        [attr.aria-expanded]="showFilters"
        aria-controls="search-filters"
        (onClick)="showFilters = !showFilters"
      ></p-button>
    </div>
    <small id="genesetSearchHelp" class="block mt-2 text-left text-color-secondary font-normal">
      Results are always gene sets. Keywords find gene sets whose name, description, publication
      (title, abstract, authors), ontology terms or genes mention them; every keyword must match, and
      <strong>OR</strong> in capitals matches either (<em>alcohol OR cocaine</em>). To find the gene
      sets that contain a gene, optionally only where its score is in a range, use
      <strong>Filters</strong> &rsaquo; <em>Gene</em>.
    </small>
    <app-search-filters
      *ngIf="showFilters"
      class="block mt-3"
      idPrefix="search-filters"
      [filters]="filters"
      (filtersChange)="filtersChanged($event)"
    ></app-search-filters>
    <p-progressBar *ngIf="isSearching" mode="indeterminate" [style]="{ height: '6px' }" styleClass="mt-2"></p-progressBar>
    <small *ngIf="errorMessage" class="block mt-2 text-orange-600 font-normal">{{ errorMessage }}</small>
  `,
})
export class GenesetSearchComponent implements OnInit, OnDestroy {
  @Output() searchExecuted = new EventEmitter<string>();
  /** The page of results now shown. */
  @Output() searchCompleted = new EventEmitter<GeneSet[]>();
  @Output() searchPaging = new EventEmitter<Paging>();
  @Output() searchCleared = new EventEmitter<boolean>();

  @ViewChild(AutoComplete) private autoComplete?: AutoComplete;

  readonly rowHeight = ROW_HEIGHT_PX;
  readonly listHeight = LIST_HEIGHT;
  readonly source: GenesetSearchSource;

  /** The typed text; an option object for a moment while one is being chosen. */
  text: string | GenesetOption = '';
  filters: SearchFilters = emptyFilters();
  sort: Sort = { by: null, order: 'asc' };
  showFilters = false;
  isSearching = false;
  errorMessage?: string;
  /** The offset of the page shown, as the paginator counts it. */
  first = 0;
  /** Results per page. */
  rows = PAGE_SIZE;
  readonly rowsPerPageOptions = [PAGE_SIZE, 50, 100];
  /** How many gene sets the search found across every page. */
  totalRecords = 0;
  /** What the results of the last search run are, e.g. "Gene sets that contain Drd2". */
  resultsDescription = '';

  private gwApi: ApiBaseService;
  private results: GeneSet[] = [];
  private lastSearch?: Subscription;
  private choosing = false;

  constructor(
    apiBaseServiceFactory: ApiBaseServiceFactory,
    private router: Router,
    private route: ActivatedRoute,
  ) {
    this.gwApi = apiBaseServiceFactory.create(environment.urls.geneWeaverApi);
    this.source = new GenesetSearchSource(this.gwApi);
  }

  get query(): string {
    return typeof this.text === 'string' ? this.text : '';
  }

  get filterCount(): number {
    return activeFilterCount(this.filters);
  }

  get searchable(): boolean {
    return canSearch(this.query, this.filters) && !filterProblem(this.filters);
  }

  /** A search in the URL -- shared, or reloaded -- runs once, as the page opens. */
  ngOnInit(): void {
    this.route.queryParams.pipe(take(1)).subscribe((params) => {
      const { filters, sort } = fromQueryParams(params);
      this.text = params['search'] ?? '';
      this.filters = filters;
      this.sort = sort;
      this.showFilters = activeFilterCount(filters) > 0;
      this.source.setFilters(filters);
      if (canSearch(this.query, filters)) {
        // Next tick: the search tells the page it started, and the page restyles itself, which
        // Angular refuses during the check that is creating this field.
        setTimeout(() => this.run(0));
      }
    });
  }

  ngOnDestroy(): void {
    this.source.destroy();
    this.lastSearch?.unsubscribe();
  }

  filtersChanged(filters: SearchFilters): void {
    this.filters = filters;
    this.source.setFilters(filters);
  }

  /** A suggestion was chosen: open that gene set. */
  open(option: GenesetOption): void {
    this.choosing = true;
    this.router.navigate(['/geneset', option.id]);
  }

  keyUp(event: KeyboardEvent): void {
    if (event.key !== 'Enter') {
      return;
    }
    if (this.choosing) {
      this.choosing = false; // That Enter chose a suggestion.
      return;
    }
    this.submit();
  }

  /** Run the full search for the text and filters, from its first page. */
  submit(): void {
    if (!this.searchable) {
      return;
    }
    // A pending suggestion search would reopen the list over the results.
    if (this.autoComplete) {
      clearTimeout(this.autoComplete.searchTimeout);
      if (this.autoComplete.overlayVisible) {
        this.autoComplete.hide();
      }
    }
    this.router.navigate([], {
      queryParams: { search: this.query.trim() || null, ...toQueryParams(this.filters, this.sort) },
      queryParamsHandling: 'merge',
    });
    this.run(0);
  }

  /** Sort the results (from the table's headers) and search again. */
  sortBy(sort: Sort): void {
    this.sort = sort;
    this.submit();
  }

  /** Show another page, or the same results with more or fewer per page (the paginator). */
  changePage(page: { first?: number; rows?: number }): void {
    this.rows = page.rows ?? this.rows;
    this.run(page.first ?? 0);
  }

  /** The paginator's report: "25 out of 1,696 gene sets shown". */
  get pageReport(): string {
    const total = this.totalRecords.toLocaleString('en-US');
    return `${this.results.length.toLocaleString('en-US')} out of ${total} gene sets shown`;
  }

  clear(): void {
    this.lastSearch?.unsubscribe();
    this.text = '';
    this.filters = emptyFilters();
    this.sort = { by: null, order: 'asc' };
    this.showFilters = false;
    this.results = [];
    this.first = 0;
    this.totalRecords = 0;
    this.isSearching = false;
    this.errorMessage = undefined;
    this.resultsDescription = '';
    this.source.reset();
    this.source.setFilters(this.filters);
    this.searchCleared.emit(true);
    this.searchCompleted.emit([]);
  }

  private run(offset: number): void {
    this.isSearching = true;
    this.errorMessage = undefined;
    this.searchExecuted.emit(this.query);
    if (offset === 0) {
      this.resultsDescription = describeSearch(this.query, this.filters);
    }
    this.lastSearch?.unsubscribe();
    this.lastSearch = this.gwApi
      .getCollection<GeneSet>(
        '/genesets/search',
        searchParams(this.query, this.filters, { offset, limit: this.rows }, this.sort),
      )
      .subscribe({
        next: (response) => {
          this.results = response.data ?? [];
          this.first = offset;
          // An API without the count still pages: the total is at least what has been seen.
          this.totalRecords = response.paging?.total_items ?? offset + this.results.length;
          this.isSearching = false;
          this.searchCompleted.emit(this.results);
          this.searchPaging.emit(response.paging);
        },
        error: (error: { error?: { detail?: unknown } }) => {
          this.isSearching = false;
          const detail = error?.error?.detail;
          this.errorMessage =
            typeof detail === 'string' ? detail : 'The search failed. Check the filters and try again.';
          if (offset === 0) {
            this.results = [];
            this.first = 0;
            this.totalRecords = 0;
          }
          this.searchCompleted.emit(this.results);
        },
      });
  }
}
