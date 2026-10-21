import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GeneSetComponent } from './geneset.component';
import { ActivatedRoute } from '@angular/router';
import { ApiBaseServiceFactory } from "jax-apiutils";
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { of } from 'rxjs';
import { SessionService } from '../../services/session.service';


describe('GeneSetComponent', () => {
  let component: GeneSetComponent;
  let fixture: ComponentFixture<GeneSetComponent>;
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
        { provide: SessionService, useValue: { authenticated: false, refresh: jest.fn() } },
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
