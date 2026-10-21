import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ApiBaseServiceFactory } from 'jax-apiutils';
import { of, throwError } from 'rxjs';

import { SessionService } from '../../../services/session.service';
import { SIMILAR_POLL_INTERVAL_MS, SimilarGenesetsComponent } from './similar-genesets.component';
import { SIMILAR } from './similar-models.spec';

describe('SimilarGenesetsComponent', () => {
  let fixture: ComponentFixture<SimilarGenesetsComponent>;
  let component: SimilarGenesetsComponent;
  let post: jest.Mock;
  let get: jest.Mock;
  const session = { authenticated: true, refresh: jest.fn() };

  beforeEach(async () => {
    post = jest.fn();
    get = jest.fn();
    session.authenticated = true;
    await TestBed.configureTestingModule({
      imports: [SimilarGenesetsComponent],
      providers: [
        provideRouter([]),
        { provide: ApiBaseServiceFactory, useValue: { create: () => ({ post, get }) } },
        { provide: SessionService, useValue: session },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(SimilarGenesetsComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('genesetId', 5);
    fixture.detectChanges();
  });

  const page = () => fixture.nativeElement as HTMLElement;

  it('does not search until asked, and asks a signed-out visitor to sign in', () => {
    expect(post).not.toHaveBeenCalled();
    session.authenticated = false;
    fixture.detectChanges();
    expect(page().textContent).toContain('Sign in to find similar gene sets');
  });

  it("sends the gene set and the run's threshold choice", () => {
    post.mockReturnValue(of({ object: { result: SIMILAR } }));
    component.thresholds.mode = 'uploader';
    component.run();
    expect(post).toHaveBeenCalledWith('/tools/similar_genesets', { geneset_id: 5, threshold: 'uploader' });
  });

  it('polls a run AsyncTask is still working on, then shows the list and charts', fakeAsync(() => {
    post.mockReturnValue(of({ object: { run_id: 11, status: 'running' } }));
    get.mockReturnValueOnce(of({ object: { status: 'running' } }));
    get.mockReturnValueOnce(of({ object: { status: 'completed', result: SIMILAR } }));
    component.run();
    expect(component.running).toBe(true);
    tick(SIMILAR_POLL_INTERVAL_MS * 2);
    fixture.detectChanges();
    expect(get).toHaveBeenCalledWith('/tools/runs/11');
    expect(component.running).toBe(false);
    expect(page().querySelectorAll('tbody tr').length).toBe(4);
    expect(page().textContent).toContain('4 of the 15,438 gene sets');
    expect(page().querySelectorAll('rect').length).toBe(4);
    expect(page().querySelectorAll('polygon[stroke-width]').length).toBe(3);
  }));

  it('says why a run failed, naming its workflow', fakeAsync(() => {
    post.mockReturnValue(of({ object: { run_id: 11, status: 'running' } }));
    get.mockReturnValue(of({ object: { status: 'failed', workflow_id: 'ats:x' } }));
    component.run();
    tick(SIMILAR_POLL_INTERVAL_MS);
    expect(component.errorMessage).toBe('The search ended failed (workflow ats:x).');
  }));

  it('passes on a refusal from the API', () => {
    post.mockReturnValue(throwError(() => ({ status: 403, error: { detail: 'Not readable' } })));
    component.run();
    expect(component.errorMessage).toBe('Not readable');
    expect(component.running).toBe(false);
  });

  it('will not send custom thresholds without a cutoff', () => {
    component.thresholds.mode = 'custom';
    component.run();
    expect(post).not.toHaveBeenCalled();
    expect(component.problem).toContain('at least one cutoff');
  });
});
