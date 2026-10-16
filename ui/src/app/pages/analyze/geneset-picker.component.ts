import {
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpParams } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { ApiBaseService, ApiBaseServiceFactory } from 'jax-apiutils';
import { Subject, Subscription, catchError, map, of, switchMap } from 'rxjs';
import { AutoComplete, AutoCompleteModule } from 'primeng/autocomplete';

import { environment } from '../../../environments/environment';
import { GeneSet } from '../../models/gene-set';
import { appendPage, GenesetOption, PAGE_SIZE, parseIds, toOption } from './geneset-picker';

interface PageRequest {
  query: string;
  offset: number;
}

interface PageResult extends PageRequest {
  options: GenesetOption[];
  failed?: boolean;
}

/** Load the next page when the list is scrolled to within this many rows of its end. */
const PREFETCH_ROWS = 5;

/**
 * Every suggestion is one fixed-height row of two lines. The virtual scroller positions rows
 * by this size, so it must match what is drawn -- the styles below pin it.
 */
export const ROW_HEIGHT_PX = 52;

/** Rows the list shows without scrolling. */
export const VISIBLE_ROWS = 10;

/** The list's own top and bottom padding (PrimeNG's 0.25rem each). */
const LIST_PADDING_PX = 8;

/**
 * The gene sets to analyse: type to search them, or type and paste ids as before.
 *
 * Searches `GET /genesets/search`, which matches ids (`167180`, `GS167180`) and words from a
 * gene set's name, description and other metadata, and returns only gene sets the caller may
 * read. Results arrive a page at a time: scrolling to the end of the list fetches the next.
 *
 * Ids stay first-class. Typing or pasting `514, 515` and pressing Enter, a comma, or leaving
 * the field adds them without a search, so a known list is as quick to enter as it was.
 *
 * Bound as `[(ids)]` to the page's list of id strings, so the page's own checks and its
 * other ways of filling the field (ABBA's "use these gene sets") are unchanged.
 */
@Component({
  selector: 'app-geneset-picker',
  standalone: true,
  imports: [CommonModule, FormsModule, AutoCompleteModule],
  // The field fills its column, and a long gene set name is cut short on its chip (the full
  // name is in the suggestion list) rather than wrapping the chip onto two lines.
  styles: [
    `
      :host ::ng-deep .p-autocomplete,
      :host ::ng-deep .p-autocomplete-multiple-container {
        width: 100%;
      }
      /* ROW_HEIGHT_PX: the virtual scroller places rows by it, so no margin may add to it. */
      :host ::ng-deep .p-autocomplete-panel .p-autocomplete-item {
        height: 52px;
        margin: 0;
        overflow: hidden;
      }
      /* The virtual list's content otherwise grows to its longest name, wider than the panel,
         and long names are clipped at the panel's edge instead of ending in an ellipsis. */
      :host ::ng-deep .p-autocomplete-panel .p-scroller-content {
        width: 100%;
      }
      :host ::ng-deep .p-autocomplete-token-label {
        max-width: 18rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    `,
  ],
  template: `
    <p-autoComplete
      [inputId]="inputId"
      [(ngModel)]="selected"
      (ngModelChange)="selectionChanged($event)"
      [suggestions]="suggestions"
      (completeMethod)="search($event.query)"
      [multiple]="true"
      [unique]="true"
      dataKey="id"
      optionLabel="chip"
      [delay]="300"
      [minLength]="1"
      [virtualScroll]="true"
      [virtualScrollItemSize]="rowHeight"
      [lazy]="true"
      (onLazyLoad)="loadMore($event.last)"
      [scrollHeight]="listHeight"
      [showEmptyMessage]="true"
      [emptyMessage]="emptyMessage"
      (onKeyUp)="keyUp($event)"
      (onBlur)="blur($event)"
      [placeholder]="selected.length ? '' : placeholder"
      [ariaLabel]="ariaLabel"
      styleClass="w-full"
      inputStyleClass="w-full"
    >
      <ng-template let-option pTemplate="item">
        <div class="geneset-option" [attr.data-gs-id]="option.id">
          <div class="white-space-nowrap overflow-hidden text-overflow-ellipsis">
            <strong>GS{{ option.id }}</strong>
            <span *ngIf="option.abbreviation" class="ml-2">{{ option.abbreviation }}</span>
          </div>
          <small *ngIf="option.detail" class="block text-color-secondary">{{ option.detail }}</small>
        </div>
      </ng-template>
    </p-autoComplete>
    <small *ngIf="loading" class="block mt-1 text-color-secondary" aria-live="polite">
      Searching gene sets…
    </small>
    <small *ngIf="failed" class="block mt-1 text-color-secondary" aria-live="polite">
      The gene set search is not responding. You can still type gene set IDs.
    </small>
  `,
})
export class GenesetPickerComponent implements OnChanges, OnDestroy {
  /** The selected gene set ids, as the page holds them. */
  @Input() ids: string[] = [];
  @Output() idsChange = new EventEmitter<string[]>();
  @Input() inputId = 'genesetIds';
  @Input() ariaLabel = 'Gene sets to analyze';
  @Input() placeholder = 'Search by name or ID, or type IDs, e.g. 514, 515';

  @ViewChild(AutoComplete) private autoComplete?: AutoComplete;

  readonly rowHeight = ROW_HEIGHT_PX;
  /** Tall enough for ten suggestions; more scroll, and load as they come into view. */
  readonly listHeight = `${VISIBLE_ROWS * ROW_HEIGHT_PX + LIST_PADDING_PX}px`;

  selected: GenesetOption[] = [];
  suggestions: GenesetOption[] = [];
  loading = false;
  failed = false;

  private gwApi: ApiBaseService;
  /** Options seen in results, so a chip keeps its label when the page rebinds the ids. */
  private known = new Map<number, GenesetOption>();
  private query = '';
  private exhausted = true;
  private requests = new Subject<PageRequest>();
  private subscription: Subscription;

  constructor(apiBaseServiceFactory: ApiBaseServiceFactory) {
    this.gwApi = apiBaseServiceFactory.create(environment.urls.geneWeaverApi);
    // switchMap: a newer request -- another keystroke, or the next page -- drops the older
    // one, so results never arrive out of order.
    this.subscription = this.requests
      .pipe(
        switchMap((request) =>
          this.gwApi
            .getCollection<GeneSet>(
              '/genesets/search',
              new HttpParams()
                .set('search_text', request.query)
                .set('limit', PAGE_SIZE)
                .set('offset', request.offset),
            )
            .pipe(
              map((response): PageResult => ({ ...request, options: (response.data ?? []).map(toOption) })),
              catchError(() => of<PageResult>({ ...request, options: [], failed: true })),
            ),
        ),
      )
      .subscribe((result) => this.receive(result));
  }

  get emptyMessage(): string {
    return parseIds(this.query)
      ? 'No readable gene set has that ID. Press Enter to add it anyway.'
      : 'No gene sets match. Try other words, or type gene set IDs.';
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['ids']) {
      const current = this.selected.map((option) => String(option.id));
      if (current.join(',') !== (this.ids ?? []).join(',')) {
        this.selected = (this.ids ?? []).map((id) => this.optionFor(id));
      }
    }
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe();
  }

  /** A new query: start again from its first page. */
  search(query: string): void {
    this.query = query.trim();
    if (!this.query) {
      this.suggestions = [];
      this.loading = false;
      return;
    }
    this.exhausted = false;
    this.fetch(0);
  }

  /** The list was scrolled; fetch the next page once the last rows come into view. */
  loadMore(lastVisible: number | undefined): void {
    if (this.exhausted || this.loading || lastVisible === undefined) {
      return;
    }
    if (lastVisible >= this.suggestions.length - PREFETCH_ROWS) {
      this.fetch(this.suggestions.length);
    }
  }

  selectionChanged(options: GenesetOption[] | null): void {
    this.selected = options ?? [];
    this.selected.forEach((option) => this.known.set(option.id, option));
    this.idsChange.emit(this.selected.map((option) => String(option.id)));
  }

  /** Enter or a comma after ids adds them as typed, without choosing a suggestion. */
  keyUp(event: KeyboardEvent): void {
    if (event.key === 'Enter' || event.key === ',') {
      this.addTyped(event.target as HTMLInputElement);
    }
  }

  /** Leaving the field keeps ids typed into it, as the old chips field did. */
  blur(event: Event): void {
    this.addTyped(event.target as HTMLInputElement);
  }

  private addTyped(input: HTMLInputElement | null): void {
    const ids = input ? parseIds(input.value) : undefined;
    if (!input || !ids) {
      return;
    }
    const present = new Set(this.selected.map((option) => option.id));
    const added = ids.filter((id) => !present.has(id) && present.add(id));
    input.value = '';
    this.query = '';
    this.suggestions = [];
    // The keystrokes that typed the ids started a debounced search; it would open the list
    // again for text that is no longer there.
    // PrimeNG's hide() touches the list's scroller, which exists only while the list is open.
    if (this.autoComplete) {
      clearTimeout(this.autoComplete.searchTimeout);
      if (this.autoComplete.overlayVisible) {
        this.autoComplete.hide();
      }
    }
    if (added.length) {
      this.selectionChanged([...this.selected, ...added.map((id) => this.optionFor(String(id)))]);
    }
  }

  private fetch(offset: number): void {
    this.loading = true;
    this.requests.next({ query: this.query, offset });
  }

  private receive(result: PageResult): void {
    if (result.query !== this.query) {
      return; // Answers a query the user has since changed.
    }
    this.loading = false;
    this.failed = !!result.failed;
    result.options.forEach((option) => this.known.set(option.id, option));
    this.suggestions = result.offset === 0 ? result.options : appendPage(this.suggestions, result.options);
    this.exhausted = !!result.failed || result.options.length < PAGE_SIZE;
  }

  private optionFor(id: string): GenesetOption {
    const numeric = Number(id);
    return this.known.get(numeric) ?? { id: numeric, chip: Number.isInteger(numeric) ? `GS${id}` : id };
  }
}
