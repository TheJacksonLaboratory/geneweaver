import { TestBed } from '@angular/core/testing';

import { FIXTURES } from './fixtures';
import { upsetModel } from './models';
import { UpsetPlotComponent } from './upset-plot.component';

describe('UpsetPlotComponent', () => {
  it('draws a bar per combination and a row of dots per gene set', () => {
    const { geneset_ids, gene_counts, intersections } = FIXTURES.upset;
    const model = upsetModel(geneset_ids, gene_counts, intersections);
    const fixture = TestBed.createComponent(UpsetPlotComponent);
    fixture.componentInstance.model = model;
    fixture.componentInstance.ngOnChanges();
    const svg: SVGSVGElement = fixture.nativeElement.querySelector('svg');

    expect(svg.getAttribute('aria-label')).toContain('UpSet');
    expect(svg.querySelectorAll('rect.bar')).toHaveLength(model.bars.length);
    // A dot per (combination, gene set), filled where the set is a member.
    expect(svg.querySelectorAll('circle').length).toBe(model.bars.length * model.sets.length);
  });

  it('hovering a column explains it and highlights its sets', () => {
    const { geneset_ids, gene_counts, intersections } = FIXTURES.upset;
    const model = upsetModel(geneset_ids, gene_counts, intersections);
    const fixture = TestBed.createComponent(UpsetPlotComponent);
    fixture.componentInstance.model = model;
    fixture.componentInstance.ngOnChanges();
    const host: HTMLElement = fixture.nativeElement;
    const tooltip = host.querySelector('.chart-tooltip') as HTMLElement;
    const hit = host.querySelector('g.column rect.hit') as SVGRectElement;
    const top = model.bars[0];

    hit.dispatchEvent(new MouseEvent('mouseenter'));
    expect(tooltip.style.display).toBe('block');
    expect(tooltip.textContent).toContain(top.sets.map((id) => `GS${id}`).join(' ∩ '));
    expect(tooltip.textContent).toContain(`Genes in exactly these sets: ${top.size}`);
    const columns = Array.from(host.querySelectorAll('g.column'));
    expect(columns[0].getAttribute('opacity')).toBe('1');
    expect(columns[1].getAttribute('opacity')).toBe('0.2');
    const sets = Array.from(host.querySelectorAll('g.set'));
    const memberRow = model.sets.findIndex((s) => top.sets.includes(s.id));
    const otherRow = model.sets.findIndex((s) => !top.sets.includes(s.id));
    expect(sets[memberRow].getAttribute('opacity')).toBe('1');
    expect(sets[otherRow].getAttribute('opacity')).toBe('0.2');

    hit.dispatchEvent(new MouseEvent('mouseleave'));
    expect(tooltip.style.display).toBe('none');
    expect(columns[1].getAttribute('opacity')).toBe('1');
  });

  it('every interactive mark is reachable by keyboard and labelled', () => {
    const { geneset_ids, gene_counts, intersections } = FIXTURES.upset;
    const fixture = TestBed.createComponent(UpsetPlotComponent);
    fixture.componentInstance.model = upsetModel(geneset_ids, gene_counts, intersections);
    fixture.componentInstance.ngOnChanges();
    const hits = Array.from(fixture.nativeElement.querySelectorAll('rect.hit')) as Element[];
    expect(hits.every((h) => h.getAttribute('tabindex') === '0')).toBe(true);
    expect(hits[0].getAttribute('aria-label')).toContain('Genes in exactly these sets');
    hits[0].dispatchEvent(new FocusEvent('focus'));
    expect((fixture.nativeElement.querySelector('.chart-tooltip') as HTMLElement).style.display).toBe('block');
  });
});
