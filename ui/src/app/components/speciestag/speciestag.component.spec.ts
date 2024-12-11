import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SpeciesTagComponent } from './speciestag.component';

describe('SpeciesTagComponent', () => {
  let component: SpeciesTagComponent;
  let fixture: ComponentFixture<SpeciesTagComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SpeciesTagComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(SpeciesTagComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
