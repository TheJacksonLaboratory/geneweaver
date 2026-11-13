import { TestBed } from '@angular/core/testing';

import { InfoTipComponent } from './info-tip.component';

describe('InfoTipComponent', () => {
  const render = async (text: string, label = '') => {
    await TestBed.configureTestingModule({ imports: [InfoTipComponent] }).compileComponents();
    const fixture = TestBed.createComponent(InfoTipComponent);
    fixture.componentRef.setInput('text', text);
    fixture.componentRef.setInput('label', label);
    fixture.detectChanges();
    return fixture.nativeElement.querySelector('.info-tip') as HTMLElement;
  };

  it('is an info icon a keyboard can reach', async () => {
    const icon = await render('Only gene sets from these species.', 'Species');
    expect(icon.classList).toContain('pi-info-circle');
    expect(icon.getAttribute('tabindex')).toBe('0');
  });

  it('gives screen readers the control and the explanation', async () => {
    const icon = await render('Only gene sets from these species.', 'Species');
    expect(icon.getAttribute('aria-label')).toBe('Species: Only gene sets from these species.');
  });

  it('reads the explanation alone when there is no label', async () => {
    const icon = await render('Only gene sets from these species.');
    expect(icon.getAttribute('aria-label')).toBe('Only gene sets from these species.');
  });
});
