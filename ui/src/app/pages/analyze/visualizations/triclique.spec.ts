import { ComponentFixture, TestBed } from '@angular/core/testing';

import { tricliqueModel, TricliqueOutput } from './models';
import { TricliqueComponent } from './triclique.component';

const CLIQUE = { group_a: ['1', '2'], group_b: ['3'], genes: ['Aa', 'Bb', 'Cc'], edges: 11 };

const OUTPUT: TricliqueOutput = {
  group_a: ['1', '2', '4'],
  group_b: ['3'],
  include_homology: true,
  shared_genes: ['Aa', 'Bb', 'Cc', 'Dd'],
  maximal_tricliques: 2,
  edge_maximum: CLIQUE,
  vertex_maximum: { group_a: ['4'], group_b: ['3'], genes: ['Aa', 'Bb', 'Cc', 'Dd'], edges: 9 },
};

describe('tricliqueModel', () => {
  it('links every member to every member of the other two parts', () => {
    const model = tricliqueModel(CLIQUE);
    expect(model.nodes.map((n) => n.part)).toEqual(['a', 'a', 'b', 'gene', 'gene', 'gene']);
    // A-B 2x1, A-genes 2x3, B-genes 1x3: the tool's own count.
    expect(model.links.length).toBe(CLIQUE.edges);
    expect(model.summary).toContain('11 links');
  });

  it('puts group A left, group B right and the genes below both', () => {
    const model = tricliqueModel(CLIQUE);
    const [a, , b, gene] = model.nodes;
    expect(a.x).toBeLessThan(gene.x);
    expect(b.x).toBeGreaterThan(gene.x);
    expect(gene.y).toBeGreaterThan(Math.max(a.y, b.y));
    expect(model.nodes.every((n) => n.x > 0 && n.x < model.width && n.y < model.height)).toBe(true);
  });
});

describe('TricliqueComponent', () => {
  let fixture: ComponentFixture<TricliqueComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [TricliqueComponent] }).compileComponents();
    fixture = TestBed.createComponent(TricliqueComponent);
  });

  function render(result: TricliqueOutput, maximum: 'edge' | 'vertex' = 'edge'): HTMLElement {
    fixture.componentRef.setInput('result', result);
    fixture.componentRef.setInput('maximum', maximum);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('draws the chosen maximum', () => {
    expect(render(OUTPUT).querySelectorAll('line').length).toBe(11);
    expect(render(OUTPUT, 'vertex').querySelectorAll('circle').length).toBe(4);
  });

  it('says so when there is no triclique', () => {
    const host = render({ ...OUTPUT, maximal_tricliques: 0, edge_maximum: null, vertex_maximum: null });
    expect(host.querySelector('svg')).toBeNull();
    expect(host.textContent).toContain('No triclique');
  });
});
