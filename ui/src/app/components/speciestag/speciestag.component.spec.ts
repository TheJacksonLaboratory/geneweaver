import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SpeciestagComponent } from './speciestag.component';

describe('SpeciesTagComponent', () => {
  let component: SpeciestagComponent;
  let fixture: ComponentFixture<SpeciestagComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SpeciestagComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(SpeciestagComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it.each([
    [1, 'Mus musculus', 'Mouse'],
    [8, 'Caenorhabditis elegans', 'Nematode'],
    [9, 'Saccharomyces cerevisiae', 'Yeast'],
    [13, 'Xenopus laevis', 'African clawed frog'],
  ])('names species %i by its id, not by position', (id, name, common) => {
    component.species_id = id;
    expect(component.getSpeciesName()).toBe(name);
    expect(component.getSpeciesCommonName()).toBe(common);
  });

  it('shows the id for a species it does not know', () => {
    component.species_id = 7;
    expect(component.getSpeciesName()).toBe('Species 7');
    expect(component.getSpeciesColor()).toBe('gray');
  });
});
