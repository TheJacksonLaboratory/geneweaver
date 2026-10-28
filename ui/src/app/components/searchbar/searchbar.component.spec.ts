import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SearchBarComponent } from './searchbar.component';
import { ApiBaseServiceFactory } from "jax-apiutils";
import { ActivatedRoute } from "@angular/router";
import { of } from "rxjs";

describe('SearchBarComponent', () => {
  let component: SearchBarComponent;
  let fixture: ComponentFixture<SearchBarComponent>;
  const mockApiBaseServiceFactory = {
    create: jest.fn().mockReturnValue({
      getCollection: jest.fn().mockReturnValue(of({ data: [] }))
    })
  };
  
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SearchBarComponent],
      providers: [
        { provide: ApiBaseServiceFactory, useValue: mockApiBaseServiceFactory },
        {
          provide: ActivatedRoute,
          useValue: {
            queryParams: of({search: 'something'})
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(SearchBarComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('tells people how to search for several terms, and the input points at it', () => {
    const root: HTMLElement = fixture.nativeElement;
    const help = root.querySelector('#search-help');
    expect(help?.textContent).toContain('OR');
    expect(help?.textContent).toContain('alcohol AND RNA-seq OR cocaine');
    expect(root.querySelector('input')?.getAttribute('aria-describedby')).toBe('search-help');
  });
});
