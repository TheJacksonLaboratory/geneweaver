/**
 * Gene set suggestions from `GET /genesets/search`, a page at a time: what the analyze page's
 * picker and the /next search field both list as you type. Not an Angular service -- each
 * field owns one, since each has its own query, filters and list.
 */
import { ApiBaseService } from 'jax-apiutils';
import { Subject, Subscription, catchError, map, of, switchMap } from 'rxjs';

import { GeneSet } from '../models/gene-set';
import { emptyFilters, filterProblem, searchParams, SearchFilters } from './search-filters';
import { appendPage, GenesetOption, PAGE_SIZE, toOption } from './geneset-options';

interface PageRequest {
  query: string;
  filters: SearchFilters;
  offset: number;
}

interface PageResult extends PageRequest {
  options: GenesetOption[];
  failed?: boolean;
}

/** Load the next page when the list is scrolled to within this many rows of its end. */
const PREFETCH_ROWS = 5;

export class GenesetSearchSource {
  suggestions: GenesetOption[] = [];
  loading = false;
  failed = false;
  /** Every option seen in a result, so a chip or label can be shown again by id. */
  readonly known = new Map<number, GenesetOption>();

  private query = '';
  private filters: SearchFilters = emptyFilters();
  private exhausted = true;
  private requests = new Subject<PageRequest>();
  private subscription: Subscription;

  constructor(private gwApi: ApiBaseService) {
    // switchMap: a newer request -- another keystroke, a filter, or the next page -- drops
    // the older one, so results never arrive out of order.
    this.subscription = this.requests
      .pipe(
        switchMap((request) =>
          this.gwApi
            .getCollection<GeneSet>(
              '/genesets/search',
              searchParams(request.query, request.filters, { offset: request.offset, limit: PAGE_SIZE }),
            )
            .pipe(
              map((response): PageResult => ({ ...request, options: (response.data ?? []).map(toOption) })),
              catchError(() => of<PageResult>({ ...request, options: [], failed: true })),
            ),
        ),
      )
      .subscribe((result) => this.receive(result));
  }

  get currentQuery(): string {
    return this.query;
  }

  /** A new query: start again from its first page. */
  search(query: string): void {
    this.query = query.trim();
    this.restart();
  }

  /** New filters apply to the query already typed. */
  setFilters(filters: SearchFilters): void {
    this.filters = filters;
    if (this.query) {
      this.restart();
    }
  }

  /** The list was scrolled; fetch the next page once its last rows come into view. */
  loadMore(lastVisible: number | undefined): void {
    if (this.exhausted || this.loading || lastVisible === undefined) {
      return;
    }
    if (lastVisible >= this.suggestions.length - PREFETCH_ROWS) {
      this.fetch(this.suggestions.length);
    }
  }

  /** Forget the query and its list, e.g. once typed ids have been added. */
  reset(): void {
    this.query = '';
    this.suggestions = [];
    this.loading = false;
    this.exhausted = true;
  }

  destroy(): void {
    this.subscription.unsubscribe();
  }

  private restart(): void {
    // Filters the API would refuse are not sent; the filter panel says what is wrong.
    if (!this.query || filterProblem(this.filters)) {
      this.suggestions = [];
      this.loading = false;
      this.exhausted = true;
      return;
    }
    this.exhausted = false;
    this.fetch(0);
  }

  private fetch(offset: number): void {
    this.loading = true;
    this.requests.next({ query: this.query, filters: this.filters, offset });
  }

  private receive(result: PageResult): void {
    if (result.query !== this.query || result.filters !== this.filters) {
      return; // Answers a query or filters the user has since changed.
    }
    this.loading = false;
    this.failed = !!result.failed;
    result.options.forEach((option) => this.known.set(option.id, option));
    this.suggestions = result.offset === 0 ? result.options : appendPage(this.suggestions, result.options);
    this.exhausted = !!result.failed || result.options.length < PAGE_SIZE;
  }
}
