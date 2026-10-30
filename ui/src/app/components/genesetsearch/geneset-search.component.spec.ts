import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpParams } from '@angular/common/http';
import { ActivatedRoute, Router } from '@angular/router';
import { ApiBaseServiceFactory } from 'jax-apiutils';
import { Observable, of, throwError } from 'rxjs';

import { GenesetSearchComponent } from './geneset-search.component';
import { GeneSetListComponent } from '../genesetlist/genesetlist.component';
import { emptyFilters } from '../../search/search-filters';

const genesets = (start: number, count: number) =>
  Array.from({ length: count }, (_, index) => ({ id: start + index, name: `Set ${start + index}` }));

describe('GenesetSearchComponent', () => {
  let fixture: ComponentFixture<GenesetSearchComponent>;
  let search: GenesetSearchComponent;
  let requests: HttpParams[];
  let respond: (params: HttpParams) => Observable<unknown>;
  let navigations: { commands: unknown[]; extras?: { queryParams?: Record<string, unknown> } }[];
  let results: unknown[][];
  let queryParams: Record<string, string>;

  const setUp = async () => {
    await TestBed.configureTestingModule({
      imports: [GenesetSearchComponent],
      providers: [
        {
          provide: ApiBaseServiceFactory,
          useValue: {
            create: () => ({
              getCollection: (_url: string, params: HttpParams) => {
                requests.push(params);
                return respond(params);
              },
            }),
          },
        },
        {
          provide: Router,
          useValue: { navigate: (commands: unknown[], extras?: never) => navigations.push({ commands, extras }) },
        },
        { provide: ActivatedRoute, useValue: { queryParams: of(queryParams) } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(GenesetSearchComponent);
    search = fixture.componentInstance;
    search.searchCompleted.subscribe((rows) => results.push(rows));
    fixture.detectChanges();
  };

  beforeEach(() => {
    requests = [];
    navigations = [];
    results = [];
    queryParams = {};
    respond = (params) =>
      of({
        data: genesets(Number(params.get('offset')) + 1, Number(params.get('limit'))),
        paging: { total_items: 1696 },
      });
  });

  it('says results are gene sets, and how keywords and the gene filter find them', async () => {
    await setUp();
    const help = (fixture.nativeElement as HTMLElement).querySelector('#genesetSearchHelp')?.textContent ?? '';
    expect(help).toContain('Results are always gene sets');
    expect(help).toContain('OR');
    expect(help).toContain('contain a gene');
  });

  it('describes the results of the search it ran, not filters edited since', async () => {
    queryParams = { search: 'alcohol', gene: 'Drd2' };
    await setUp();
    await new Promise((resolve) => setTimeout(resolve));
    expect(search.resultsDescription).toContain('contain Drd2');
    search.filtersChanged({ ...emptyFilters(), gene: 'Tp53' });
    expect(search.resultsDescription).toContain('contain Drd2');
    search.clear();
    expect(search.resultsDescription).toBe('');
  });

  it('runs a search shared in the URL once, with its filters and sort', async () => {
    queryParams = { search: 'dopamine', species: '1', sort: 'size', order: 'desc' };
    await setUp();
    await new Promise((resolve) => setTimeout(resolve));
    expect(requests).toHaveLength(1);
    expect(requests[0].get('search_text')).toBe('dopamine');
    expect(requests[0].getAll('species')).toEqual(['Mus Musculus']);
    expect(requests[0].get('sort_by')).toBe('size');
    expect(search.showFilters).toBe(true);
    expect(results.at(-1)).toHaveLength(25);
  });

  it('does nothing on open without a search in the URL', async () => {
    await setUp();
    expect(requests).toEqual([]);
  });

  it('submits on Enter: the URL records the search, and the results are emitted', async () => {
    await setUp();
    search.text = 'dopamine';
    search.keyUp({ key: 'Enter' } as KeyboardEvent);
    expect(navigations[0].extras?.queryParams).toMatchObject({ search: 'dopamine', sort: null });
    expect(requests[0].get('offset')).toBe('0');
    expect(results.at(-1)).toHaveLength(25);
    expect(search.totalRecords).toBe(1696);
    expect(search.pageReport).toBe('25 out of 1,696 gene sets shown');
  });

  it('opens a chosen suggestion instead of searching', async () => {
    await setUp();
    search.text = 'dopamine';
    search.open({ id: 167180, chip: 'GS167180' });
    search.keyUp({ key: 'Enter' } as KeyboardEvent);
    expect(navigations).toEqual([{ commands: ['/geneset', 167180], extras: undefined }]);
    expect(requests).toEqual([]);
  });

  it('searches by a gene alone, and not with filters the API would refuse', async () => {
    await setUp();
    search.filtersChanged({ ...emptyFilters(), pValue: 0.05 });
    search.text = '';
    expect(search.searchable).toBe(false);
    search.submit();
    expect(requests).toEqual([]);

    search.filtersChanged({ ...emptyFilters(), gene: 'Drd2', pValue: 0.05 });
    expect(search.searchable).toBe(true);
    search.submit();
    expect(requests[0].get('gene')).toBe('Drd2');
    expect(requests[0].get('p_value')).toBe('0.05');
  });

  it('sorts from the table by searching again from the first page', async () => {
    await setUp();
    search.text = 'dopamine';
    search.submit();
    search.sortBy({ by: 'species', order: 'asc' });
    expect(requests.at(-1)!.get('sort_by')).toBe('species');
    expect(requests.at(-1)!.get('offset')).toBe('0');
    expect(navigations.at(-1)!.extras?.queryParams).toMatchObject({ sort: 'species' });
  });

  it('shows one page at a time, replacing the last, with the total over every page', async () => {
    await setUp();
    search.text = 'dopamine';
    search.submit();
    search.changePage({ first: 50, rows: 25 });
    expect(requests.at(-1)!.get('offset')).toBe('50');
    expect(results.at(-1)!.map((row) => (row as { id: number }).id)).toEqual(
      Array.from({ length: 25 }, (_, index) => 51 + index),
    );
    expect(search.first).toBe(50);
    expect(search.totalRecords).toBe(1696);

    respond = () => of({ data: genesets(1676, 21), paging: { total_items: 1696 } });
    search.changePage({ first: 1675, rows: 25 });
    expect(search.pageReport).toBe('21 out of 1,696 gene sets shown');
  });

  it('asks for as many rows as the paginator shows, and starts a new search on page one', async () => {
    await setUp();
    search.text = 'dopamine';
    search.submit();
    search.changePage({ first: 100, rows: 100 });
    expect(requests.at(-1)!.get('limit')).toBe('100');
    search.sortBy({ by: 'size', order: 'desc' });
    expect(requests.at(-1)!.get('offset')).toBe('0');
    expect(requests.at(-1)!.get('limit')).toBe('100');
    expect(search.first).toBe(0);
  });

  it('still pages against an API that sends no total', async () => {
    await setUp();
    respond = () => of({ data: genesets(26, 25), paging: {} });
    search.text = 'dopamine';
    search.changePage({ first: 25, rows: 25 });
    expect(search.totalRecords).toBe(50);
  });

  it("shows the API's reason when a search is refused", async () => {
    await setUp();
    respond = () => throwError(() => ({ status: 422, error: { detail: 'Give search_text, a gene, or both.' } }));
    search.text = 'dopamine';
    search.submit();
    expect(search.errorMessage).toBe('Give search_text, a gene, or both.');
    expect(results.at(-1)).toEqual([]);
    expect(search.totalRecords).toBe(0);
  });

  it('clears everything, as the logo does', async () => {
    queryParams = { search: 'dopamine', gene: 'Drd2' };
    await setUp();
    await new Promise((resolve) => setTimeout(resolve));
    search.clear();
    expect(search.query).toBe('');
    expect(search.filters).toEqual(emptyFilters());
    expect(results.at(-1)).toEqual([]);
    expect([search.first, search.totalRecords]).toEqual([0, 0]);
  });
});

describe('GeneSetListComponent sorting', () => {
  it('sorts ascending, then descending, then not at all', async () => {
    await TestBed.configureTestingModule({
      imports: [GeneSetListComponent],
      providers: [{ provide: Router, useValue: { navigate: () => undefined } }],
    }).compileComponents();
    const list = TestBed.createComponent(GeneSetListComponent).componentInstance;
    const emitted: unknown[] = [];
    list.sortChange.subscribe((sort) => emitted.push(sort));

    list.toggleSort('size');
    list.sort = { by: 'size', order: 'asc' };
    list.toggleSort('size');
    list.sort = { by: 'size', order: 'desc' };
    list.toggleSort('size');
    list.toggleSort('species');
    expect(emitted).toEqual([
      { by: 'size', order: 'asc' },
      { by: 'size', order: 'desc' },
      { by: null, order: 'asc' },
      { by: 'species', order: 'asc' },
    ]);
    expect(list.ariaSort('size')).toBe('descending');
    expect(list.sortIcon('name')).toBe('pi pi-sort-alt');
  });
});
