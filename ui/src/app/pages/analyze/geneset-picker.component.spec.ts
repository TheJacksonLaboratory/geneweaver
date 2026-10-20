import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpParams } from '@angular/common/http';
import { ApiBaseServiceFactory } from 'jax-apiutils';
import { Observable, of, Subject, throwError } from 'rxjs';

import { GenesetPickerComponent } from './geneset-picker.component';
import { ROW_HEIGHT_PX, VISIBLE_ROWS } from '../../search/suggestion-list';
import { emptyFilters } from '../../search/search-filters';
import { PAGE_SIZE } from '../../search/geneset-options';

/** `count` gene sets from `start`, as `GET /genesets/search` returns them. */
const page = (start: number, count: number) =>
  Array.from({ length: count }, (_, index) => ({
    id: start + index,
    abbreviation: `Set ${start + index}`,
    species_id: 1,
    curation_id: 3,
    score_type: 3,
    count: 10,
  }));

describe('GenesetPickerComponent', () => {
  let fixture: ComponentFixture<GenesetPickerComponent>;
  let picker: GenesetPickerComponent;
  let requests: { url: string; params: HttpParams }[];
  let respond: (params: HttpParams) => Observable<unknown>;
  let emitted: string[][];
  /** Gene sets this caller may read, for `GET /genesets?gs_id=`; anything else is refused. */
  let readable: Set<number>;
  let lookupFails: boolean;

  const apiStub = {
    getCollection: (url: string, params: HttpParams) => {
      requests.push({ url, params });
      if (url === '/genesets') {
        if (lookupFails) {
          return throwError(() => new Error('502'));
        }
        const id = Number(params.get('gs_id'));
        return of({ data: readable.has(id) ? [{ id, abbreviation: `Set ${id}`, species_id: 1 }] : [] });
      }
      return respond(params);
    },
  };


  beforeEach(async () => {
    requests = [];
    emitted = [];
    readable = new Set([514, 515, 516]);
    lookupFails = false;
    respond = (params) => of({ data: page(Number(params.get('offset')) + 1, PAGE_SIZE) });
    await TestBed.configureTestingModule({
      imports: [GenesetPickerComponent],
      providers: [
        {
          provide: ApiBaseServiceFactory,
          useValue: { create: () => apiStub } as unknown as ApiBaseServiceFactory,
        },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(GenesetPickerComponent);
    picker = fixture.componentInstance;
    picker.idsChange.subscribe((ids) => emitted.push(ids));
    fixture.detectChanges();
  });

  /** A keyboard event from the picker's input holding `value`. */
  const typed = (value: string, key: string) => {
    const input = document.createElement('input');
    input.value = value;
    return { input, event: { key, target: input } as unknown as KeyboardEvent };
  };

  it('searches gene sets the caller can read, a page at a time', () => {
    picker.search(' dopamine ');
    expect(requests).toHaveLength(1);
    expect(requests[0].url).toBe('/genesets/search');
    expect(requests[0].params.get('search_text')).toBe('dopamine');
    expect(requests[0].params.get('limit')).toBe(String(PAGE_SIZE));
    expect(requests[0].params.get('offset')).toBe('0');
    expect(picker.source.suggestions).toHaveLength(PAGE_SIZE);
    expect(picker.source.suggestions[0]).toMatchObject({ id: 1, chip: 'GS1 · Set 1' });
    expect(picker.source.loading).toBe(false);
  });

  it('fetches the next page when the list is scrolled near its end, and only then', () => {
    picker.search('dopamine');
    picker.source.loadMore(5);
    expect(requests).toHaveLength(1);

    picker.source.loadMore(PAGE_SIZE - 2);
    expect(requests).toHaveLength(2);
    expect(requests[1].params.get('offset')).toBe(String(PAGE_SIZE));
    expect(picker.source.suggestions).toHaveLength(PAGE_SIZE * 2);
    expect(picker.source.suggestions[PAGE_SIZE].id).toBe(PAGE_SIZE + 1);
  });

  it('stops paging after a short page: there is nothing more', () => {
    respond = () => of({ data: page(1, 3) });
    picker.search('rare words');
    picker.source.loadMore(2);
    expect(requests).toHaveLength(1);
  });

  it('drops an answer to a query the user has since changed', () => {
    const slow = new Subject<unknown>();
    respond = (params) => (params.get('search_text') === 'dop' ? slow : of({ data: page(100, 2) }));
    picker.search('dop');
    picker.search('dopamine');
    slow.next({ data: page(1, 5) });
    expect(picker.source.suggestions.map((option) => option.id)).toEqual([100, 101]);
  });

  it('says the search failed, and still accepts typed ids', () => {
    respond = () => throwError(() => new Error('502'));
    picker.search('dopamine');
    expect(picker.source.failed).toBe(true);
    expect(picker.source.loading).toBe(false);

    const { input, event } = typed('514', 'Enter');
    picker.keyUp(event);
    expect(emitted.at(-1)).toEqual(['514']);
    expect(input.value).toBe('');
  });

  it('does not add a typed id the user may not read, and says why', () => {
    // GS51 and GS54 do not exist on dev; a private gene set is refused the same way.
    picker.keyUp(typed('514, 51, 54', 'Enter').event);
    expect(emitted.at(-1)).toEqual(['514']);
    expect(picker.selected.map((option) => option.chip)).toEqual(['GS514 · Set 514']);
    expect(picker.rejected).toContain('Not added: GS51, GS54');
    expect(picker.rejected).toContain('private to someone else, or not exist');
  });

  it('reports every refused id when they are typed one comma at a time', () => {
    picker.keyUp(typed('514,', ',').event);
    picker.keyUp(typed('51,', ',').event);
    picker.keyUp(typed('54', 'Enter').event);
    expect(emitted.at(-1)).toEqual(['514']);
    expect(picker.rejected).toContain('Not added: GS51, GS54');

    picker.selectionChanged([]); // The user changes the chips: the note goes.
    expect(picker.rejected).toBeUndefined();
  });

  it('adds nothing it could not check', () => {
    lookupFails = true;
    picker.keyUp(typed('514', 'Enter').event);
    expect(emitted).toEqual([]);
    expect(picker.rejected).toContain('Could not check GS514');
  });

  it('lists the gene set with a typed id first, above text matches for the number', () => {
    picker.search('515');
    expect(requests.some((request) => request.url === '/genesets' && request.params.get('gs_id') === '515')).toBe(true);
    expect(picker.source.suggestions[0]).toMatchObject({ id: 515, chip: 'GS515 · Set 515' });
    expect(picker.source.suggestions).toHaveLength(PAGE_SIZE + 1);

    picker.search('51');
    expect(picker.source.suggestions[0].id).toBe(1); // No GS51 to put first: text matches only.
  });

  it('adds a picked suggestion and emits ids as the page holds them', () => {
    picker.search('dopamine');
    picker.selectionChanged([picker.source.suggestions[2]]);
    expect(emitted.at(-1)).toEqual(['3']);
  });

  it('adds typed or pasted ids on Enter, a comma, or leaving the field, without repeats', () => {
    let { event } = typed('514, GS515', 'Enter');
    picker.keyUp(event);
    expect(emitted.at(-1)).toEqual(['514', '515']);

    ({ event } = typed('515,', ','));
    picker.keyUp(event);
    expect(emitted).toHaveLength(1); // 515 is already there.

    const { input } = typed('516', 'Tab');
    picker.blur({ target: input } as unknown as Event);
    expect(emitted.at(-1)).toEqual(['514', '515', '516']);
    // Looked up, so each chip carries its gene set's name.
    expect(picker.selected.map((option) => option.chip)).toEqual([
      'GS514 · Set 514',
      'GS515 · Set 515',
      'GS516 · Set 516',
    ]);
  });

  it('leaves words in the field as a search', () => {
    const { input, event } = typed('dopamine', 'Enter');
    picker.keyUp(event);
    expect(emitted).toEqual([]);
    expect(input.value).toBe('dopamine');
  });

  it('shows ids the page sets, keeping labels it has already seen', () => {
    picker.search('dopamine');
    picker.selectionChanged([picker.source.suggestions[0]]);
    picker.ids = ['1', '999'];
    picker.ngOnChanges({ ids: { currentValue: picker.ids } as never });
    expect(picker.selected.map((option) => option.chip)).toEqual(['GS1 · Set 1', 'GS999']);
  });

  it('narrows the suggestions by the filters, and searches again when they change', () => {
    picker.search('dopamine');
    expect(requests[0].params.getAll('species')).toBeNull();

    picker.filters = { ...emptyFilters(), species: [1, 2], tiers: [3] };
    picker.ngOnChanges({ filters: { currentValue: picker.filters } as never });
    expect(requests).toHaveLength(2);
    expect(requests[1].params.getAll('species')).toEqual(['Mus Musculus', 'Homo Sapiens']);
    expect(requests[1].params.getAll('curation_tier')).toEqual(['Tier III']);
    expect(requests[1].params.get('search_text')).toBe('dopamine');
  });

  it('does not send filters the API would refuse', () => {
    picker.search('dopamine');
    picker.filters = { ...emptyFilters(), pValue: 0.05 }; // a cutoff with no gene
    picker.ngOnChanges({ filters: { currentValue: picker.filters } as never });
    expect(requests).toHaveLength(1);
    expect(picker.source.suggestions).toEqual([]);
  });

  it('sizes the list for at least ten suggestions', () => {
    expect(VISIBLE_ROWS).toBeGreaterThanOrEqual(10);
    expect(parseInt(picker.listHeight, 10)).toBeGreaterThanOrEqual(VISIBLE_ROWS * ROW_HEIGHT_PX);
    expect(picker.rowHeight).toBe(ROW_HEIGHT_PX);
  });

  it('renders an autocomplete on the labelled input id', () => {
    const input = (fixture.nativeElement as HTMLElement).querySelector('input#genesetIds');
    expect(input).not.toBeNull();
  });
});
