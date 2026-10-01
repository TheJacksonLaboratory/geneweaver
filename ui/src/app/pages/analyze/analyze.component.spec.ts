import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ApiBaseServiceFactory } from 'jax-apiutils';
import { Observable, of, throwError } from 'rxjs';

import { AnalyzeComponent } from './analyze.component';

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
      providers: [{ provide: ApiBaseServiceFactory, useValue: mockApiBaseServiceFactory }],
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
    expect(posted.at(-1)?.body).toMatchObject({ parameters: { epsilon: 1, min_points: 2 } });

    component.selectedTool = 'boolean_algebra';
    component.run();
    expect(posted.at(-1)?.body).toMatchObject({ parameters: { relation: 'intersection' } });
  });
});
