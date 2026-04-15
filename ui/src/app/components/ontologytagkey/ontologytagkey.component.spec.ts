import { ComponentFixture, TestBed } from '@angular/core/testing';
import { OntologyTagKeyComponent } from './ontologytagkey.component';

describe('OntologyTagKeyComponent', () => {
  let component: OntologyTagKeyComponent;
  let fixture: ComponentFixture<OntologyTagKeyComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OntologyTagKeyComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(OntologyTagKeyComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
