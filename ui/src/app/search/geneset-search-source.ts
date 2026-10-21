/**
 * Gene set suggestions from `GET /genesets/search`, a page at a time: what the analyze page's
 * picker and the /next search field both list as you type. Not an Angular service -- each
 * field owns one, since each has its own query, filters and list.
 *
 * A query that is gene set ids ("51", "GS514 515") also looks each id up, and lists the ones
 * the user may read first: text search matches "51" anywhere in a gene set's metadata, so
 * without this the gene set *numbered* 51 could be missing, or buried under others.
 */
import { HttpParams } from '@angular/common/http';
import { ApiBaseService } from 'jax-apiutils';
import { Observable, Subject, Subscription, catchError, forkJoin, map, of, switchMap } from 'rxjs';

import { GeneSet } from '../models/gene-set';
import { emptyFilters, filterProblem, searchParams, SearchFilters } from './search-filters';
import { appendPage, GenesetOption, PAGE_SIZE, parseIds, toOption } from './geneset-options';

/** Ids looked up individually as the user types; more is a list being pasted, not a search. */
const MAX_ID_LOOKUPS = 5;

/** What looking ids up found: the gene sets the user may read, and the ids they may not. */
export interface IdLookup {
  found: GenesetOption[];
  /** Private to someone else, or no such gene set: the API does not say which. */
  unreadable: number[];
  /** The lookup itself failed, so these ids could not be checked. */
  unchecked: number[];
}

interface PageRequest {
  query: string;
  filters: SearchFilters;
  offset: number;
}

interface PageResult extends PageRequest {
  options: GenesetOption[];
  /** The search page's own length: where the next page starts, and whether there is one. */
  pageLength: number;
  failed?: boolean;
  /** Why the API refused the search (a 4xx detail), when it said. */
  refused?: string;
}

/** Load the next page when the list is scrolled to within this many rows of its end. */
const PREFETCH_ROWS = 5;

/**
 * The API's reason for refusing a search (a 4xx with a detail), as one line; `undefined` for
 * a server or network failure, which is not the user's to fix.
 */
function refusal(error: { status?: number; error?: { detail?: unknown } }): string | undefined {
  if (!error?.status || error.status < 400 || error.status >= 500) {
    return undefined;
  }
  const detail = error.error?.detail;
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    // FastAPI's validation errors: [{loc, msg, ...}].
    return detail
      .map((item: { msg?: string; loc?: unknown[] }) =>
        [item.loc?.filter((part) => part !== 'query').join('.'), item.msg].filter(Boolean).join(': '),
      )
      .join('; ');
  }
  return 'The search was refused; check the filters.';
}

export class GenesetSearchSource {
  suggestions: GenesetOption[] = [];
  loading = false;
  /** The search could not be reached, or failed on the server. */
  failed = false;
  /** The API refused the search and said why, e.g. a cutoff out of range. */
  refused?: string;
  /** Every option seen in a result, so a chip or label can be shown again by id. */
  readonly known = new Map<number, GenesetOption>();

  private query = '';
  private filters: SearchFilters = emptyFilters();
  private exhausted = true;
  /**
   * Where the next page of the *search* starts. Not `suggestions.length`: an id query leads
   * with looked-up gene sets that are not search rows, and repeats are dropped, so counting
   * the list skipped or repeated rows at each page boundary.
   */
  private searchOffset = 0;
  private requests = new Subject<PageRequest>();
  private subscription: Subscription;

  constructor(private gwApi: ApiBaseService) {
    // switchMap: a newer request -- another keystroke, a filter, or the next page -- drops
    // the older one, so results never arrive out of order.
    this.subscription = this.requests
      .pipe(switchMap((request) => this.page(request)))
      .subscribe((result) => this.receive(result));
  }

  /**
   * Look gene set ids up: which exist and this user may read. Each is checked by
   * `GET /genesets/search?gs_id=`, so a typed id follows the same rule as the suggestions
   * (and a tool run's access check): the owner, sharing groups and projects, and admins and
   * curators may read a private gene set.
   */
  lookup(ids: number[]): Observable<IdLookup> {
    if (!ids.length) {
      return of({ found: [], unreadable: [], unchecked: [] });
    }
    return forkJoin(
      ids.map((id) =>
        this.gwApi
          .getCollection<GeneSet>('/genesets/search', new HttpParams().set('gs_id', id).set('limit', 1))
          .pipe(
            map((response) => ({ id, geneset: (response.data ?? []).find((row) => row.id === id) ?? null })),
            catchError(() => of({ id, geneset: undefined })),
          ),
      ),
    ).pipe(
      map((rows) => {
        const found = rows.filter((row) => row.geneset).map((row) => toOption(row.geneset as GeneSet));
        found.forEach((option) => this.known.set(option.id, option));
        return {
          found,
          unreadable: rows.filter((row) => row.geneset === null).map((row) => row.id),
          unchecked: rows.filter((row) => row.geneset === undefined).map((row) => row.id),
        };
      }),
    );
  }

  /** One page of the search; the first page of an id query leads with those ids. */
  private page(request: PageRequest): Observable<PageResult> {
    const search = this.gwApi
      .getCollection<GeneSet>(
        '/genesets/search',
        searchParams(request.query, request.filters, { offset: request.offset, limit: PAGE_SIZE }),
      )
      .pipe(
        map((response): GenesetOption[] | { refused?: string } => (response.data ?? []).map(toOption)),
        catchError((error: { status?: number; error?: { detail?: unknown } }) =>
          of({ refused: refusal(error) }),
        ),
      );
    const ids = request.offset === 0 ? (parseIds(request.query) ?? []) : [];
    const exact = ids.length && ids.length <= MAX_ID_LOOKUPS ? this.lookup(ids) : of(null);
    return forkJoin([search, exact]).pipe(
      map(([result, lookup]): PageResult => {
        const leading = lookup?.found ?? [];
        const page = Array.isArray(result) ? result : null;
        const refused = Array.isArray(result) ? undefined : result.refused;
        return {
          ...request,
          options: appendPage(leading, page ?? []),
          pageLength: page?.length ?? 0,
          failed: page === null && !refused && !leading.length,
          refused,
        };
      }),
    );
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
      this.fetch(this.searchOffset);
    }
  }

  /** Forget the query and its list, e.g. once typed ids have been added. */
  reset(): void {
    this.query = '';
    this.suggestions = [];
    this.loading = false;
    this.exhausted = true;
    this.searchOffset = 0;
    this.refused = undefined;
  }

  destroy(): void {
    this.subscription.unsubscribe();
  }

  private restart(): void {
    this.searchOffset = 0;
    this.refused = undefined;
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
    this.refused = result.refused;
    result.options.forEach((option) => this.known.set(option.id, option));
    this.suggestions = result.offset === 0 ? result.options : appendPage(this.suggestions, result.options);
    this.searchOffset = result.offset + result.pageLength;
    this.exhausted = !!result.failed || !!result.refused || result.pageLength < PAGE_SIZE;
  }
}
