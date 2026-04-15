import { ComponentFixture, TestBed } from '@angular/core/testing';
import { OntologyAnnotationsComponent } from './ontologyannotations.component';

describe('OntologyAnnotationsComponent', () => {
  let component: OntologyAnnotationsComponent;
  let fixture: ComponentFixture<OntologyAnnotationsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OntologyAnnotationsComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(OntologyAnnotationsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
