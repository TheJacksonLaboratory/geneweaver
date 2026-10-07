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

    const bars = svg.querySelectorAll('g > g > rect');
    expect(svg.getAttribute('aria-label')).toContain('UpSet');
    // A bar per combination, plus one size bar per gene set.
    expect(bars.length).toBe(model.bars.length + model.sets.length);
    // A dot per (combination, gene set), filled where the set is a member.
    expect(svg.querySelectorAll('circle').length).toBe(model.bars.length * model.sets.length);
    const titles = Array.from(svg.querySelectorAll('title')).map((t) => t.textContent);
    expect(titles).toContain(`GS${geneset_ids[0]}: ${gene_counts[String(geneset_ids[0]) as keyof typeof gene_counts]} genes`);
  });
});
