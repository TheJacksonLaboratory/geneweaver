import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GeneListComponent } from './genelist.component';
import { ApiBaseServiceFactory } from "jax-apiutils";
import { of } from 'rxjs';

describe('GeneListComponent', () => {
  let component: GeneListComponent;
  let fixture: ComponentFixture<GeneListComponent>;
  const mockApiBaseServiceFactory = {
    create: jest.fn().mockReturnValue({
      getCollection: jest.fn().mockReturnValue(of({ data: [] }))
    })
  };
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GeneListComponent],
      providers: [
        { provide: ApiBaseServiceFactory, useValue: mockApiBaseServiceFactory },
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(GeneListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
