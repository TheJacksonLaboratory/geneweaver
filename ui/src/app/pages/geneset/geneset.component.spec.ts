import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GeneSetComponent } from './geneset.component';
import { Router } from '@angular/router';
import { ActivatedRoute } from '@angular/router';
import { ApiBaseServiceFactory } from "jax-apiutils";
import { MockService } from "ng-mocks";
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { of } from 'rxjs';


describe('GeneSetComponent', () => {
  let component: GeneSetComponent;
  let fixture: ComponentFixture<GeneSetComponent>;
  let router: Router;
  const mockApiBaseServiceFactory = {
    create: jest.fn().mockReturnValue({
      getCollection: jest.fn().mockReturnValue(of({ data: [] }))
    })
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GeneSetComponent, NoopAnimationsModule],
      providers: [
        { provide: ApiBaseServiceFactory, useValue: mockApiBaseServiceFactory },
        {
          provide: ActivatedRoute,
          useValue: {
            params: of({ id: '123' }),
            snapshot: {
              paramMap: new Map<string, string>()
            }
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(GeneSetComponent);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
    
    component.geneset = {
      id: '123',
      genes: []
    };

    component.geneset_values = []
    
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
