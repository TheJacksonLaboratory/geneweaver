import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpParams } from '@angular/common/http';
import { provideRouter, Router } from '@angular/router';
import { ApiBaseServiceFactory } from 'jax-apiutils';
import { Observable, of, throwError } from 'rxjs';

import { AnalysesComponent, RUNS_PER_PAGE, statusTag } from './analyses.component';
import { SessionService } from '../../services/session.service';
import { ToolRunList, ToolRunSummary } from '../../runs/tool-runs';

const sessionStub = {
  authenticated: true,
  get current() {
    return { loginAvailable: true, authenticated: this.authenticated };
  },
  refresh: jest.fn(),
  signInUrl: () => '/api/sessions/login',
};

function run(overrides: Partial<ToolRunSummary> = {}): ToolRunSummary {
  return {
    run_id: 7,
    tool: 'upset',
    name: 'upset run',
    geneset_ids: [1, 2],
    status: 'completed',
    stalled: false,
    problem: null,
    created: '2026-11-25T10:00:00',
    can_rerun: true,
    ...overrides,
  };
}

function list(runs: ToolRunSummary[], extra: Partial<ToolRunList> = {}): ToolRunList {
  return { runs, total: runs.length, expired: 0, expiring: 0, retention_days: 90, ...extra };
}

describe('AnalysesComponent', () => {
  let fixture: ComponentFixture<AnalysesComponent>;
  let component: AnalysesComponent;
  let requests: { method: string; path: string; params?: string }[];
  let listing: () => Observable<unknown>;
  let rerunAnswer: () => Observable<unknown>;
  let deleteAnswer: () => Observable<unknown>;
  let navigated: unknown[][];

  const apiStub = {
    get: (path: string, params?: HttpParams) => {
      requests.push({ method: 'GET', path, params: params?.toString() });
      return listing();
    },
    post: (path: string) => {
      requests.push({ method: 'POST', path });
      return rerunAnswer();
    },
    delete: (path: string) => {
      requests.push({ method: 'DELETE', path });
      return deleteAnswer();
    },
  };

  beforeEach(async () => {
    requests = [];
    navigated = [];
    listing = () => of({ object: list([run(), run({ run_id: 6, status: 'failed', problem: 'The run failed.', tool: 'mset' })]) });
    rerunAnswer = () => of({ object: { run_id: 8, rerun_of: 7 } });
    deleteAnswer = () => of({ object: null });
    sessionStub.authenticated = true;
    TestBed.resetTestingModule();
    await TestBed.configureTestingModule({
      imports: [AnalysesComponent],
      providers: [
        { provide: ApiBaseServiceFactory, useValue: { create: () => apiStub } as unknown as ApiBaseServiceFactory },
        { provide: SessionService, useValue: sessionStub },
        provideRouter([]),
      ],
    }).compileComponents();
    const router = TestBed.inject(Router);
    jest.spyOn(router, 'navigate').mockImplementation((commands, extras) => {
      navigated.push([commands, extras]);
      return Promise.resolve(true);
    });
    fixture = TestBed.createComponent(AnalysesComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  const host = () => fixture.nativeElement as HTMLElement;
  const rows = () => Array.from(host().querySelectorAll('tr.run-row'));

  it('lists the runs, the first page, once', () => {
    const gets = requests.filter((r) => r.method === 'GET');
    expect(gets).toEqual([
      { method: 'GET', path: '/tools/runs', params: `limit=${RUNS_PER_PAGE}&offset=0` },
    ]);
    expect(rows().map((row) => row.getAttribute('data-run-id'))).toEqual(['7', '6']);
    expect(rows()[0].textContent).toContain('UpSet');
    expect(rows()[0].textContent).toContain('GS1');
    expect(rows()[1].textContent).toContain('MSET');
    expect(rows()[1].textContent).toContain('The run failed.');
  });

  it('offers download for completed runs only', () => {
    expect(rows()[0].querySelector('app-run-actions')).not.toBeNull();
    expect(rows()[1].querySelector('app-run-actions')).toBeNull();
  });

  it('says what retention did on this visit', async () => {
    listing = () => of({ object: list([run()], { expired: 3, expiring: 2 }) });
    component.load(0);
    fixture.detectChanges();

    const note = host().querySelector('.expiry-note')?.textContent ?? '';
    expect(note).toContain('3 older than 90 days were just deleted');
    expect(note).toContain('2 more are past that');
  });

  it('fetches the page the table asks for', () => {
    component.onPage({ first: 25, rows: 25 });

    expect(requests.at(-1)).toEqual({ method: 'GET', path: '/tools/runs', params: 'limit=25&offset=25' });
  });

  it('opens a run on the Analyze page', () => {
    component.open(run());

    expect(navigated).toEqual([[['/analyze'], { queryParams: { run: 7 } }]]);
  });

  it('reruns a run and follows the new one to the Analyze page', () => {
    component.rerun(run());

    expect(requests).toContainEqual({ method: 'POST', path: '/tools/runs/7/rerun' });
    expect(navigated).toEqual([[['/analyze'], { queryParams: { run: 8 } }]]);
    expect(component.busy.size).toBe(0);
  });

  describe('deleting', () => {
    const original = window.confirm;
    let confirm: jest.Mock;

    beforeEach(() => {
      confirm = jest.fn();
      // jsdom has no confirm dialog to spy on.
      window.confirm = confirm;
    });

    afterEach(() => {
      window.confirm = original;
    });

    it('deletes a run once confirmed, then lists again', () => {
      confirm.mockReturnValue(true);

      component.remove(run());

      expect(confirm.mock.calls[0][0]).toContain('UpSet run 7');
      expect(requests).toContainEqual({ method: 'DELETE', path: '/tools/runs/7' });
      expect(requests.filter((r) => r.method === 'GET')).toHaveLength(2);
    });

    it('does not delete without confirmation', () => {
      confirm.mockReturnValue(false);

      component.remove(run());

      expect(requests.some((r) => r.method === 'DELETE')).toBe(false);
    });
  });

  it('explains a failed action', () => {
    rerunAnswer = () => throwError(() => ({ status: 409, error: { detail: 'Run it again from Analyze.' } }));

    component.rerun(run());

    expect(component.errorMessage).toBe('Run it again from Analyze.');
    expect(navigated).toEqual([]);
  });

  it('asks a signed-out visitor to sign in', () => {
    listing = () => throwError(() => ({ status: 401 }));
    sessionStub.authenticated = false;

    component.load(0);
    fixture.detectChanges();

    expect(component.errorMessage).toBe('Sign in to see your analyses.');
    expect(sessionStub.refresh).toHaveBeenCalled();
    expect(host().textContent).toContain('Sign in to see your analyses.');
  });
});

describe('statusTag', () => {
  it('shows a stalled run as stalled, whatever its status', () => {
    expect(statusTag(run({ status: 'running', stalled: true }))).toEqual({ value: 'Stalled', severity: 'warn' });
    expect(statusTag(run({ status: 'timed_out' }))).toEqual({ value: 'timed out', severity: 'secondary' });
    expect(statusTag(run({ status: 'failed' })).severity).toBe('danger');
  });
});
