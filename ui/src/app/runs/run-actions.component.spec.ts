import { ComponentFixture, TestBed } from '@angular/core/testing';

import { RunActionsComponent } from './run-actions.component';
import { environment } from '../../environments/environment';

describe('RunActionsComponent', () => {
  let fixture: ComponentFixture<RunActionsComponent>;
  let component: RunActionsComponent;

  async function create(inputs: Record<string, unknown>): Promise<void> {
    await TestBed.configureTestingModule({ imports: [RunActionsComponent] }).compileComponents();
    fixture = TestBed.createComponent(RunActionsComponent);
    component = fixture.componentInstance;
    for (const [name, value] of Object.entries(inputs)) {
      fixture.componentRef.setInput(name, value);
    }
    fixture.detectChanges();
    await fixture.whenStable();
  }

  const host = () => fixture.nativeElement as HTMLElement;

  it("links each of the tool's downloads to the API", async () => {
    await create({ runId: 12, tool: 'combine' });

    const urls = component.downloadItems().map((item) => item.url);
    const base = environment.urls.geneWeaverApi;
    expect(urls).toContain(`${base}/tools/runs/12/download?format=csv&table=matrix`);
    expect(urls).toContain(`${base}/tools/runs/12/download?format=odemat`);
    expect(urls).toContain(`${base}/tools/runs/12/download?format=json`);
    expect(host().textContent).toContain('Run 12');
  });

  it('asks for a rerun, once, and hides Rerun where the run cannot be rerun', async () => {
    await create({ runId: 12, tool: 'upset' });
    const asked: unknown[] = [];
    component.rerun.subscribe(() => asked.push(true));

    const rerun = Array.from(host().querySelectorAll('button')).find((b) => b.textContent?.includes('Rerun'));
    rerun?.click();
    expect(asked).toHaveLength(1);

    fixture.componentRef.setInput('canRerun', false);
    fixture.detectChanges();
    expect(host().textContent).not.toContain('Rerun');
  });

  it('disables Rerun while a rerun is being submitted', async () => {
    await create({ runId: 12, tool: 'upset', rerunning: true });

    const rerun = Array.from(host().querySelectorAll('button')).find((b) => b.textContent?.includes('Rerun'));
    expect(rerun?.disabled).toBe(true);
  });
});
