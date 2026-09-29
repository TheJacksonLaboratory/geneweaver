import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MockService } from 'ng-mocks';
import { ApiBaseServiceFactory } from 'jax-apiutils';

import { AnalyzeComponent } from './analyze.component';

/**
 * The bounds under test mirror `UpSetRequest` in `api/schemas/tools.py`: at least 2 and at
 * most 20 gene sets, dropping to 10 when empty combinations are expanded. The page must not
 * enable a run the API is known to reject.
 */
describe('AnalyzeComponent', () => {
  let component: AnalyzeComponent;
  let fixture: ComponentFixture<AnalyzeComponent>;
  const mockApiBaseServiceFactory = MockService(ApiBaseServiceFactory);

  /** Distinct, valid ids -- the count is what matters here, not the values. */
  const ids = (count: number): string[] =>
    Array.from({ length: count }, (_, index) => String(index + 1));

  beforeEach(async () => {
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

    it('cannot run a tool that is not yet available', () => {
      component.genesetIdInput = ids(2);
      component.selectedTool = 'phenomemap';
      expect(component.selectedToolReason).toBeDefined();
      expect(component.canRun).toBe(false);
    });

    it('cannot run while a run is in flight', () => {
      component.genesetIdInput = ids(2);
      component.running = true;
      expect(component.canRun).toBe(false);
    });
  });
});
