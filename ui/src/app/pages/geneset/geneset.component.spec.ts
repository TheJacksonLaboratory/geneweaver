import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GeneSetComponent } from './geneset.component';

describe('GeneSetComponent', () => {
  let component: GeneSetComponent;
  let fixture: ComponentFixture<GeneSetComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GeneSetComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(GeneSetComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
