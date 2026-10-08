import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ApiBaseServiceFactory } from 'jax-apiutils';
import { Observable, of, throwError } from 'rxjs';

import { AnalyzeComponent, RUN_POLL_INTERVAL_MS } from './analyze.component';
import { SessionService } from '../../services/session.service';
import { provideRouter } from '@angular/router';
import { ABBA_FIXTURE } from './visualizations/abba-fixture';

/** A signed-in session; analyses require one. Tests of the signed-out page set it to false. */
const sessionStub = {
  authenticated: true,
  get current() {
    return { loginAvailable: true, authenticated: this.authenticated };
  },
  refresh: () => undefined,
  signInUrl: () => '/api/sessions/login?next=%2Fnext%2Fanalyze',
  signOutUrl: () => '/api/sessions/logout',
};
const sessionProvider = { provide: SessionService, useValue: sessionStub };

/** What `GET /tools` returns: every registered tool, runnable or not. */
const TOOL_LIST = {
  upset: { available: true, reason: null, caveat: null },
  hypergeometric: { available: true, reason: null, caveat: null },
  dbscan: { available: true, reason: null, caveat: null },
  combine: { available: true, reason: null, caveat: null },
  boolean_algebra: { available: true, reason: null, caveat: null },
  jaccard_clustering: { available: true, reason: null, caveat: null },
  jaccard_similarity: { available: true, reason: null, caveat: 'p-values need distributions' },
  mset: { available: false, reason: 'MSET needs the MSETcpp binary', caveat: null },
  phenome_map: { available: false, reason: 'PhenomeMap needs biclique', caveat: null },
};

/**
 * The bounds under test mirror `UpSetRequest` in `api/schemas/tools.py`: at least 2 and at
 * most 20 gene sets, dropping to 10 when empty combinations are expanded. The page must not
 * enable a run the API is known to reject.
 */
describe('AnalyzeComponent', () => {
  let component: AnalyzeComponent;
  let fixture: ComponentFixture<AnalyzeComponent>;
  let posted: { path: string; body: unknown }[];
  let toolsResponse: () => Observable<unknown>;

  /** A stub standing in for the real API client, since the component now fetches on init. */
  const apiStub = {
    get: (path: string) =>
      path === '/tools' ? toolsResponse() : of({ object: {} }),
    post: (path: string, body: unknown) => {
      posted.push({ path, body });
      return of({ object: { tool: 'stub', geneset_ids: [], gene_counts: {}, result: {} } });
    },
  };
  const mockApiBaseServiceFactory = { create: () => apiStub } as unknown as ApiBaseServiceFactory;

  /** Distinct, valid ids -- the count is what matters here, not the values. */
  const ids = (count: number): string[] =>
    Array.from({ length: count }, (_, index) => String(index + 1));

  beforeEach(async () => {
    posted = [];
    toolsResponse = () => of({ object: { tools: TOOL_LIST } });
    await TestBed.configureTestingModule({
      imports: [AnalyzeComponent],
      providers: [
        { provide: ApiBaseServiceFactory, useValue: mockApiBaseServiceFactory },
        sessionProvider,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(AnalyzeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  describe('gene set count bounds', () => {
    it('cannot run below the lower bound', () => {
      component.genesetIdInput = ids(1);
      expect(component.canRun).toBe(false);
    });

    it('can run at the lower bound', () => {
      component.genesetIdInput = ids(2);
      expect(component.canRun).toBe(true);
      expect(component.limitViolation).toBeUndefined();
    });

    it('can run at the upper bound', () => {
      component.genesetIdInput = ids(20);
      expect(component.canRun).toBe(true);
      expect(component.limitViolation).toBeUndefined();
    });

    it('cannot run one past the upper bound', () => {
      component.genesetIdInput = ids(21);
      expect(component.canRun).toBe(false);
      expect(component.limitViolation).toContain('at most 20');
    });

    it('reports nothing while the user is still below two entries', () => {
      component.genesetIdInput = ids(1);
      expect(component.limitViolation).toBeUndefined();
    });
  });

  describe('include_zeros lowers the bound', () => {
    // UpSet-only: it is the tool that expands every combination, and the only one whose
    // endpoint takes the flag.
    beforeEach(() => {
      component.selectedTool = 'upset';
    });

    it('can run at the zero-expansion bound', () => {
      component.genesetIdInput = ids(10);
      component.includeZeros = true;
      expect(component.canRun).toBe(true);
    });

    it('cannot run one past it', () => {
      component.genesetIdInput = ids(11);
      component.includeZeros = true;
      expect(component.canRun).toBe(false);
      expect(component.limitViolation).toContain('limited to 10 gene sets');
    });

    it('allows the same count with the checkbox cleared', () => {
      component.genesetIdInput = ids(11);
      component.includeZeros = false;
      expect(component.canRun).toBe(true);
    });
  });

  describe('other run gates', () => {
    it('cannot run with an unparseable entry', () => {
      component.genesetIdInput = [...ids(2), 'abc'];
      expect(component.invalidEntries).toEqual(['abc']);
      expect(component.canRun).toBe(false);
    });

    it('cannot run a tool the API reports as unavailable', () => {
      component.genesetIdInput = ids(2);
      component.selectedTool = 'mset';
      expect(component.selectedToolReason).toContain('MSETcpp');
      expect(component.canRun).toBe(false);
    });

    it('cannot run while a run is in flight', () => {
      component.genesetIdInput = ids(2);
      component.running = true;
      expect(component.canRun).toBe(false);
    });
  });
});


describe('AnalyzeComponent tool list', () => {
  let component: AnalyzeComponent;
  let fixture: ComponentFixture<AnalyzeComponent>;
  let toolsResponse: () => Observable<unknown>;
  let posted: { path: string; body: unknown }[];

  const apiStub = {
    get: (path: string) => (path === '/tools' ? toolsResponse() : of({ object: {} })),
    post: (path: string, body: unknown) => {
      posted.push({ path, body });
      return of({ object: { tool: 'stub', geneset_ids: [], gene_counts: {}, result: {} } });
    },
  };

  const build = async () => {
    await TestBed.configureTestingModule({
      imports: [AnalyzeComponent],
      providers: [
        {
          provide: ApiBaseServiceFactory,
          useValue: { create: () => apiStub } as unknown as ApiBaseServiceFactory,
        },
        sessionProvider,
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(AnalyzeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  };

  beforeEach(() => {
    posted = [];
    toolsResponse = () => of({ object: { tools: TOOL_LIST } });
    TestBed.resetTestingModule();
  });

  it('lists every registered tool, not a hand-picked subset', async () => {
    await build();
    expect(component.tools).toHaveLength(9);
    // The four that used to be missing entirely.
    const names = component.tools.map((tool) => tool.value);
    expect(names).toContain('boolean_algebra');
    expect(names).toContain('combine');
    expect(names).toContain('jaccard_clustering');
    expect(names).toContain('jaccard_similarity');
  });

  it('marks the tools the API cannot run, with the reason', async () => {
    await build();
    const blocked = component.tools.filter((tool) => tool.disabledReason);
    expect(blocked.map((tool) => tool.value).sort()).toEqual(['mset', 'phenome_map']);
    expect(blocked[0].disabledReason).toBeTruthy();
  });

  it('puts runnable tools before blocked ones', async () => {
    await build();
    const firstBlocked = component.tools.findIndex((tool) => !!tool.disabledReason);
    const lastRunnable = component.tools.reduce(
      (acc, tool, index) => (tool.disabledReason ? acc : index),
      -1,
    );
    expect(lastRunnable).toBeLessThan(firstBlocked);
  });

  it('selects a runnable tool by default', async () => {
    await build();
    expect(component.selectedToolReason).toBeUndefined();
  });

  it('surfaces a caveat for a tool that runs but qualifies its result', async () => {
    await build();
    component.selectedTool = 'jaccard_similarity';
    expect(component.selectedToolCaveat).toContain('distributions');
  });

  it('cannot run before the list has loaded', async () => {
    toolsResponse = () => new Observable(); // never emits
    await build();
    component.genesetIdInput = ['1', '2'];
    expect(component.toolsLoading).toBe(true);
    expect(component.canRun).toBe(false);
  });

  it('reports a failure to load the list instead of silently offering nothing', async () => {
    toolsResponse = () => throwError(() => ({ status: 500 }));
    await build();
    expect(component.toolsError).toBeTruthy();
    expect(component.canRun).toBe(false);
  });

  it('sends UpSet to its own endpoint and others to the generic one', async () => {
    await build();
    component.genesetIdInput = ['1', '2'];

    component.selectedTool = 'upset';
    component.run();
    expect(posted.at(-1)?.path).toBe('/tools/upset');

    component.selectedTool = 'dbscan';
    component.run();
    expect(posted.at(-1)?.path).toBe('/tools/dbscan');
  });
});

/**
 * Each tool's options, with legacy's defaults from `odestatic.tool_param`, and the exact
 * body each sends. Defaults are sent explicitly because legacy's are not always the API's.
 */
describe('AnalyzeComponent tool options', () => {
  let component: AnalyzeComponent;
  let fixture: ComponentFixture<AnalyzeComponent>;
  let posted: { path: string; body: unknown }[];

  const apiStub = {
    get: (path: string) =>
      path === '/tools'
        ? of({
            object: {
              // Every tool runnable here: the options are under test, not availability.
              tools: Object.fromEntries(
                Object.keys(TOOL_LIST).map((key) => [key, { available: true }]),
              ),
            },
          })
        : of({ object: {} }),
    post: (path: string, body: unknown) => {
      posted.push({ path, body });
      return of({ object: { tool: 'stub', geneset_ids: [], gene_counts: {}, result: {} } });
    },
  };

  beforeEach(async () => {
    posted = [];
    TestBed.resetTestingModule();
    await TestBed.configureTestingModule({
      imports: [AnalyzeComponent],
      providers: [
        {
          provide: ApiBaseServiceFactory,
          useValue: { create: () => apiStub } as unknown as ApiBaseServiceFactory,
        },
        sessionProvider,
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(AnalyzeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
    component.genesetIdInput = ['1', '2'];
  });

  /** Select a tool, render, and return the page. */
  const choose = async (tool: string): Promise<HTMLElement> => {
    component.selectedTool = tool;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  };

  const runAndRead = () => {
    component.run();
    return posted.at(-1)!;
  };

  it.each([
    ['upset', '/tools/upset', { geneset_ids: [1, 2], include_homology: true, include_zeros: false }],
    [
      'jaccard_similarity',
      '/tools/jaccard_similarity',
      {
        geneset_ids: [1, 2],
        parameters: { include_homology: true, pairwise_deletion: false, p_value_threshold: 1.0 },
      },
    ],
    [
      'jaccard_clustering',
      '/tools/jaccard_clustering',
      { geneset_ids: [1, 2], parameters: { include_homology: true, method: 'ward' } },
    ],
    [
      'hypergeometric',
      '/tools/hypergeometric',
      { geneset_ids: [1, 2], parameters: { include_homology: true, pairwise_deletion: false } },
    ],
    ['combine', '/tools/combine', { geneset_ids: [1, 2], parameters: { include_homology: true } }],
    [
      'boolean_algebra',
      '/tools/boolean_algebra',
      { geneset_ids: [1, 2], parameters: { relation: 'union' } },
    ],
    [
      'dbscan',
      '/tools/dbscan',
      { geneset_ids: [1, 2], parameters: { include_homology: true, epsilon: 1, min_points: 1 } },
    ],
    ['mset', '/tools/mset', { geneset_ids: [1, 2], parameters: { number_of_samples: 5000 } }],
    [
      'phenome_map',
      '/tools/phenome_map',
      {
        geneset_ids: [1, 2],
        parameters: {
          include_homology: true,
          disable_bootstrap: false,
          use_fdr: false,
          p_value_threshold: 1.0,
          min_genes: 1,
          max_level: 40,
        },
      },
    ],
  ])('%s sends legacy\'s defaults', async (tool, path, body) => {
    await choose(tool);
    const sent = runAndRead();
    expect(sent.path).toBe(path);
    expect(sent.body).toEqual(body);
  });

  it('JaccardSimilarity sends a changed pairwise deletion and p-value from the form', async () => {
    const page = await choose('jaccard_similarity');
    const pairwise = page.querySelector<HTMLInputElement>('#option-pairwise_deletion')!;
    pairwise.click();
    const threshold = page.querySelector<HTMLSelectElement>('#option-p_value_threshold')!;
    // The choices are legacy's, labels as written.
    expect(Array.from(threshold.options).map((option) => option.textContent?.trim())).toEqual([
      '1.0',
      '0.5',
      '0.10',
      '0.05',
      '0.01',
    ]);
    threshold.selectedIndex = 3;
    threshold.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    expect(runAndRead().body).toEqual({
      geneset_ids: [1, 2],
      parameters: { include_homology: true, pairwise_deletion: true, p_value_threshold: 0.05 },
    });
  });

  it('Homology can be excluded, and the radio group is labelled', async () => {
    const page = await choose('combine');
    const legend = page.querySelector('fieldset legend');
    expect(legend?.textContent).toContain('Homology');
    const excluded = page.querySelector<HTMLInputElement>('#option-include_homology-1')!;
    expect(page.querySelector(`label[for="${excluded.id}"]`)?.textContent).toBe('Excluded');
    excluded.click();
    fixture.detectChanges();
    expect(runAndRead().body).toEqual({
      geneset_ids: [1, 2],
      parameters: { include_homology: false },
    });
  });

  it('JaccardClustering sends the method in lower case', async () => {
    const page = await choose('jaccard_clustering');
    const method = page.querySelector<HTMLSelectElement>('#option-method')!;
    expect(Array.from(method.options).map((option) => option.textContent?.trim())).toEqual([
      'Ward',
      'Single',
      'Centroid',
      'McQuitty',
      'Average',
      'Complete',
    ]);
    method.selectedIndex = 4;
    method.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(runAndRead().body).toMatchObject({ parameters: { method: 'average' } });
  });

  it('BooleanAlgebra shows "at least N" only for an intersection, and sends it then', async () => {
    let page = await choose('boolean_algebra');
    expect(page.querySelector('#option-at_least')).toBeNull();

    page.querySelector<HTMLInputElement>('#option-relation-1')!.click(); // Intersection
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    page = fixture.nativeElement;
    const atLeast = page.querySelector<HTMLInputElement>('#option-at_least');
    expect(atLeast).not.toBeNull();
    expect(atLeast!.getAttribute('aria-describedby')).toBe('option-at_least-help');

    component.optionValues['at_least'] = 3;
    expect(runAndRead().body).toEqual({
      geneset_ids: [1, 2],
      parameters: { relation: 'intersection', at_least: 3 },
    });
  });

  it('labels the symmetric difference as legacy does, sending "except"', async () => {
    const page = await choose('boolean_algebra');
    const except = page.querySelector<HTMLInputElement>('#option-relation-2')!;
    expect(page.querySelector(`label[for="${except.id}"]`)?.textContent).toBe(
      'Symmetric difference',
    );
    except.click();
    fixture.detectChanges();
    expect(runAndRead().body).toMatchObject({ parameters: { relation: 'except' } });
  });

  it('MSET sends the chosen number of trials', async () => {
    const page = await choose('mset');
    const trials = page.querySelector<HTMLSelectElement>('#option-number_of_samples')!;
    trials.selectedIndex = 1;
    trials.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(runAndRead().body).toEqual({
      geneset_ids: [1, 2],
      parameters: { number_of_samples: 10000 },
    });
  });

  it('does not offer PhenomeMap options the v3 tool cannot honour', async () => {
    const page = await choose('phenome_map');
    const text = page.textContent ?? '';
    expect(text).not.toContain('Permutation');
    expect(text).not.toContain('Max in node');
    // A default that is not the first choice is the one shown selected.
    const maxLevel = page.querySelector<HTMLSelectElement>('#option-max_level')!;
    expect(maxLevel.options[maxLevel.selectedIndex].textContent?.trim()).toBe('40');
  });

  it('resets the options to their defaults when the tool changes', async () => {
    await choose('dbscan');
    component.optionValues['epsilon'] = 4;
    component.optionValues['include_homology'] = false;
    await choose('combine');
    await choose('dbscan');
    expect(component.optionValues).toEqual({ include_homology: true, epsilon: 1, min_points: 1 });
  });

  it('cannot run with a blank or zero DBSCAN option, and says why', async () => {
    await choose('dbscan');
    component.optionValues['epsilon'] = 0;
    fixture.detectChanges();
    expect(component.canRun).toBe(false);
    expect(fixture.nativeElement.textContent).toContain('Epsilon must be a whole number of at least 1');

    component.optionValues['epsilon'] = null as unknown as number; // a cleared number input
    expect(component.canRun).toBe(false);

    component.optionValues['epsilon'] = 2;
    expect(component.canRun).toBe(true);
  });
});

/**
 * A run AsyncTask has not finished within the API's wait comes back as 202 with a run id.
 * The page must poll it, not treat that body as a completed, empty result.
 */
describe('AnalyzeComponent pending runs', () => {
  let component: AnalyzeComponent;
  let fixture: ComponentFixture<AnalyzeComponent>;
  let postBody: unknown;
  let pollResponses: unknown[];
  let polled: string[];

  const PENDING = {
    tool: 'dbscan',
    geneset_ids: [1, 2],
    gene_counts: { '1': 3, '2': 4 },
    caveat: null,
    run_id: 42,
    status: 'running',
  };

  const apiStub = {
    get: (path: string) => {
      if (path === '/tools') {
        return of({ object: { tools: TOOL_LIST } });
      }
      polled.push(path);
      return of({ object: pollResponses.shift() });
    },
    post: () => of({ object: postBody }),
  };

  beforeEach(async () => {
    polled = [];
    pollResponses = [];
    TestBed.resetTestingModule();
    await TestBed.configureTestingModule({
      imports: [AnalyzeComponent],
      providers: [
        {
          provide: ApiBaseServiceFactory,
          useValue: { create: () => apiStub } as unknown as ApiBaseServiceFactory,
        },
        sessionProvider,
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(AnalyzeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
    component.genesetIdInput = ['1', '2'];
    jest.useFakeTimers();
  });

  afterEach(() => {
    component.ngOnDestroy();
    jest.useRealTimers();
  });

  it('polls a pending ABBA search to its result page', () => {
    postBody = { tool: 'abba', geneset_ids: [], gene_counts: {}, caveat: null, run_id: 43, status: 'running' };
    pollResponses = [{ run_id: 43, status: 'completed', result: ABBA_FIXTURE }];
    component.selectedTool = 'abba';
    component.abbaGenesText = 'Drd2';

    component.run();
    expect(component.pendingRunId).toBe(43);
    expect(component.abbaResult).toBeUndefined();

    jest.advanceTimersByTime(RUN_POLL_INTERVAL_MS);
    expect(polled).toEqual(['/tools/runs/43']);
    expect(component.running).toBe(false);
    expect(component.abbaResult).toBe(ABBA_FIXTURE);
    expect(component.abbaRanAt).toBeInstanceOf(Date);
    expect(component.genericResult).toBeUndefined();
  });

  it('polls a pending run through a running poll to its result', () => {
    postBody = PENDING;
    pollResponses = [
      { run_id: 42, status: 'running', result: null },
      { run_id: 42, status: 'completed', result: { clusters: [], ran: true } },
    ];
    component.selectedTool = 'dbscan';

    component.run();
    // Accepted, not finished: still running, nothing rendered as a result yet.
    expect(component.running).toBe(true);
    expect(component.pendingRunId).toBe(42);
    expect(component.genericResult).toBeUndefined();

    jest.advanceTimersByTime(RUN_POLL_INTERVAL_MS);
    expect(polled).toEqual(['/tools/runs/42']);
    expect(component.running).toBe(true);

    jest.advanceTimersByTime(RUN_POLL_INTERVAL_MS);
    expect(polled).toHaveLength(2);
    expect(component.running).toBe(false);
    expect(component.pendingRunId).toBeUndefined();
    expect(component.genericResult).toEqual({
      tool: 'dbscan',
      geneset_ids: [1, 2],
      gene_counts: { '1': 3, '2': 4 },
      caveat: null,
      result: { clusters: [], ran: true },
    });

    // Finished means finished: no further polls.
    jest.advanceTimersByTime(RUN_POLL_INTERVAL_MS * 3);
    expect(polled).toHaveLength(2);
  });

  it('rebuilds the UpSet result from the raw tool output', () => {
    postBody = { ...PENDING, tool: 'upset' };
    pollResponses = [
      {
        run_id: 42,
        status: 'completed',
        result: { intersections: [{ genesets: ['1', '2'], size: 2 }] },
      },
    ];
    component.selectedTool = 'upset';

    component.run();
    jest.advanceTimersByTime(RUN_POLL_INTERVAL_MS);

    expect(component.result).toEqual({
      tool: 'UpSet',
      geneset_ids: [1, 2],
      gene_counts: { '1': 3, '2': 4 },
      intersections: [{ geneset_ids: ['1', '2'], size: 2 }],
    });
  });

  it('reports a run that stops without completing as an error', () => {
    postBody = PENDING;
    pollResponses = [{ run_id: 42, status: 'failed', workflow_id: 'ats:GeneWeaverTools:x' }];
    component.selectedTool = 'dbscan';

    component.run();
    jest.advanceTimersByTime(RUN_POLL_INTERVAL_MS);

    expect(component.running).toBe(false);
    expect(component.genericResult).toBeUndefined();
    expect(component.errorMessage).toContain('ended failed');
    expect(component.errorMessage).toContain('ats:GeneWeaverTools:x');
  });

  it('stops polling when cleared', () => {
    postBody = PENDING;
    pollResponses = [{ run_id: 42, status: 'running' }];
    component.selectedTool = 'dbscan';

    component.run();
    component.clear();
    jest.advanceTimersByTime(RUN_POLL_INTERVAL_MS * 3);

    expect(polled).toHaveLength(0);
    expect(component.running).toBe(false);
  });

  it('does not mistake a completed result that carries a run id for a pending one', () => {
    postBody = {
      tool: 'dbscan',
      geneset_ids: [1, 2],
      gene_counts: {},
      run_id: 42,
      executed_by: 'asynctask',
      result: { ran: true },
    };
    component.selectedTool = 'dbscan';

    component.run();

    expect(component.running).toBe(false);
    expect(component.pendingRunId).toBeUndefined();
    expect(component.genericResult?.result).toEqual({ ran: true });
  });
});

describe('AnalyzeComponent signed out', () => {
  let component: AnalyzeComponent;
  let fixture: ComponentFixture<AnalyzeComponent>;

  const apiStub = {
    get: () => of({ object: { tools: TOOL_LIST } }),
    post: () => of({ object: {} }),
  };

  beforeEach(async () => {
    sessionStub.authenticated = false;
    TestBed.resetTestingModule();
    await TestBed.configureTestingModule({
      imports: [AnalyzeComponent],
      providers: [
        {
          provide: ApiBaseServiceFactory,
          useValue: { create: () => apiStub } as unknown as ApiBaseServiceFactory,
        },
        sessionProvider,
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(AnalyzeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    sessionStub.authenticated = true;
  });

  it('cannot run an analysis', () => {
    component.genesetIdInput = ['1', '2'];
    expect(component.canRun).toBe(false);
  });

  it('says why, with a way to sign in that returns here', () => {
    fixture.detectChanges();
    const notice: HTMLElement = fixture.nativeElement.querySelector('.sign-in-required');
    expect(notice.textContent).toContain('requires signing in');
    expect(notice.querySelector('a')?.getAttribute('href')).toBe(
      '/api/sessions/login?next=%2Fnext%2Fanalyze',
    );
  });
});

/** `POST /tools/abba` once the search has finished: every tool run's envelope. */
function completed(result: unknown) {
  return {
    tool: 'abba',
    geneset_ids: [],
    gene_counts: {},
    caveat: null,
    executed_by: 'asynctask',
    run_id: 11,
    result,
  };
}

describe('AnalyzeComponent ABBA gene search', () => {
  let component: AnalyzeComponent;
  let fixture: ComponentFixture<AnalyzeComponent>;
  let posted: { path: string; body: unknown }[];
  let answer: () => Observable<unknown>;

  const apiStub = {
    get: () =>
      of({ object: { tools: { ...TOOL_LIST, abba: { available: true, reason: null, caveat: null } } } }),
    post: (path: string, body: unknown) => {
      posted.push({ path, body });
      return answer();
    },
  };

  beforeEach(async () => {
    posted = [];
    answer = () => of({ object: completed(ABBA_FIXTURE) });
    TestBed.resetTestingModule();
    await TestBed.configureTestingModule({
      imports: [AnalyzeComponent],
      providers: [
        {
          provide: ApiBaseServiceFactory,
          useValue: { create: () => apiStub } as unknown as ApiBaseServiceFactory,
        },
        sessionProvider,
        provideRouter([]),
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(AnalyzeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
    // Let the tool picker settle on its default before choosing ABBA, or its pending model
    // write lands afterwards and selects UpSet again.
    await fixture.whenStable();
    component.selectedTool = 'abba';
    fixture.detectChanges();
    await fixture.whenStable();
  });

  const host = () => fixture.nativeElement as HTMLElement;

  it('is in the tool picker, by its legacy name', () => {
    expect(component.toolOptions.find((tool) => tool.value === 'abba')?.label).toBe('ABBA gene search');
  });

  it('cannot run with neither seed genes nor gene sets', () => {
    expect(component.canRun).toBe(false);
    expect(component.abbaProblem).toBeUndefined(); // Not an error: nothing entered yet.
  });

  it('runs with seed genes alone -- no gene sets needed', () => {
    component.abbaGenesText = 'Drd2, Drd1';
    expect(component.canRun).toBe(true);
  });

  it('runs with a single gene set alone', () => {
    component.genesetIdInput = ['167180'];
    expect(component.canRun).toBe(true);
  });

  it("posts legacy's defaults: homology, Auto thresholds, tiers 1-3, every species", () => {
    component.abbaGenesText = 'Drd2\nDrd1\ndrd2';
    component.run();
    expect(posted).toEqual([
      {
        path: '/tools/abba',
        body: {
          genes: ['Drd2', 'Drd1'],
          geneset_ids: [],
          include_homology: true,
          min_genes: null,
          min_genesets: null,
          tiers: [1, 2, 3],
          species_ids: null,
        },
      },
    ]);
  });

  it('posts the options as changed in the form', () => {
    component.abbaGenesText = 'Drd2 Drd1 Th';
    component.genesetIdInput = ['167180'];
    fixture.detectChanges();
    const el = host();
    el.querySelector<HTMLInputElement>('#abbaHomology')!.click();
    const minGenes = el.querySelector<HTMLSelectElement>('#abbaMinGenes')!;
    // Auto, then 1-3: one per seed gene typed, as legacy offered.
    expect(minGenes.options).toHaveLength(4);
    minGenes.selectedIndex = 2;
    minGenes.dispatchEvent(new Event('input'));
    const minGenesets = el.querySelector<HTMLSelectElement>('#abbaMinGenesets')!;
    expect(minGenesets.options).toHaveLength(51);
    minGenesets.selectedIndex = 5;
    minGenesets.dispatchEvent(new Event('input'));
    el.querySelector<HTMLInputElement>('#abbaTier1')!.click();
    el.querySelector<HTMLInputElement>('#abbaTier4')!.click();
    el.querySelector<HTMLInputElement>('#abbaRestrict')!.click();
    fixture.detectChanges();
    el.querySelector<HTMLInputElement>('#abbaSpecies2')!.click();
    el.querySelector<HTMLInputElement>('#abbaSpecies1')!.click();
    component.run();
    expect(posted[0].body).toEqual({
      genes: ['Drd2', 'Drd1', 'Th'],
      geneset_ids: [167180],
      include_homology: false,
      min_genes: 2,
      min_genesets: 5,
      tiers: [2, 3, 4],
      species_ids: [1, 2],
    });
  });

  it('needs at least one curation tier', () => {
    component.abbaGenesText = 'Drd2';
    component.abbaOptions.tiers = [];
    expect(component.canRun).toBe(false);
    expect(component.abbaProblem).toBe('Choose at least one curation tier.');
  });

  it('needs a species when restricting to species, and shows the list only then', () => {
    component.abbaGenesText = 'Drd2';
    fixture.detectChanges();
    expect(host().querySelector('#abbaSpecies1')).toBeNull();
    component.abbaOptions.restrictSpecies = true;
    fixture.detectChanges();
    expect(host().querySelector('#abbaSpecies1')).not.toBeNull();
    expect(component.canRun).toBe(false);
    expect(component.abbaProblem).toContain('at least one species');
  });

  it('allows one gene set, and refuses more than twenty', () => {
    component.genesetIdInput = Array.from({ length: 21 }, (_, i) => String(i + 1));
    expect(component.canRun).toBe(false);
    expect(component.abbaProblem).toContain('at most 20');
    expect(component.limitViolation).toBeUndefined();
  });

  it('says a search can take a while, then shows the result', () => {
    component.abbaGenesText = 'Drd2';
    let finish!: (value: unknown) => void;
    answer = () => new Observable((subscriber) => {
      finish = (value) => {
        subscriber.next(value);
        subscriber.complete();
      };
    });
    component.run();
    fixture.detectChanges();
    expect(host().textContent).toContain('can take up to a minute');
    finish({ object: completed(ABBA_FIXTURE) });
    fixture.detectChanges();
    expect(component.abbaResult).toBe(ABBA_FIXTURE);
    expect(component.abbaRanAt).toBeInstanceOf(Date);
    expect(host().querySelector('app-abba-result')).not.toBeNull();
    expect(host().textContent).toContain('Highly connected gene sets');
  });

  it('explains a busy server', () => {
    component.abbaGenesText = 'Drd2';
    answer = () => throwError(() => ({ status: 503, error: {} }));
    component.run();
    expect(component.errorMessage).toBe('The server is busy with other searches. Try again in a minute.');
    expect(component.running).toBe(false);
  });

  it('hands gene sets picked in the result back to the form, for another tool', () => {
    component.useGenesets([282317, 259156]);
    expect(component.genesetIdInput).toEqual(['282317', '259156']);
    expect(component.selectedTool).toBe('upset');
  });

  it('resets its options on returning to it from another tool', () => {
    component.abbaOptions.tiers = [5];
    component.selectedTool = 'upset';
    component.selectedTool = 'abba';
    expect(component.abbaOptions.tiers).toEqual([1, 2, 3]);
  });
});
