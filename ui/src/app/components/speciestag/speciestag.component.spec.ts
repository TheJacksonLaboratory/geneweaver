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
});
