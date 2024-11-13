import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SearchBarComponent } from './searchbar.component';
import { MockModule, MockService } from "ng-mocks";
import { APIBaseService } from "../../jaxapiutils/services/api-base.service";
import {ActivatedRoute} from "@angular/router";

describe('SearchBarComponent', () => {
  let component: SearchBarComponent;
  let fixture: ComponentFixture<SearchBarComponent>;
  const mockAPIBaseService = MockService(APIBaseService);

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SearchBarComponent],
      providers: [
        { provide: APIBaseService, useValue: mockAPIBaseService },
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(SearchBarComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
