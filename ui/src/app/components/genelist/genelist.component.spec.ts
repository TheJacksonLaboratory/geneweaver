import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GeneListComponent } from './genelist.component';

describe('GeneListComponent', () => {
  let component: GeneListComponent;
  let fixture: ComponentFixture<GeneListComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GeneListComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(GeneListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
