import { ComponentFixture, TestBed } from '@angular/core/testing';
import { OntologyTagComponent } from './ontologytag.component';

describe('OntologyTagComponent', () => {
  let component: OntologyTagComponent;
  let fixture: ComponentFixture<OntologyTagComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OntologyTagComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(OntologyTagComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
