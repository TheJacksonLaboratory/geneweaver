import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HomeComponent } from './home.component';
import { SearchBarComponent } from "../../components/searchbar/searchbar.component";
import { GeneSetListComponent } from "../../components/genesetlist/genesetlist.component";
import { Paging } from "../../jaxapiutils/models/api-interfaces";
import { GeneSet } from "../../models/gene-set";
import { By } from '@angular/platform-browser';
import { MockService } from "ng-mocks";
import { APIBaseService } from "../../jaxapiutils/services/api-base.service";
import { ActivatedRoute } from "@angular/router";
import { of } from "rxjs";

describe('HomeComponent', () => {
  let component: HomeComponent;
  let fixture: ComponentFixture<HomeComponent>;
  const mockAPIBaseService = MockService(APIBaseService);
  const mockGeneset = {
    "id": 36435,
    "user_id": 623,
    "file_id": 70425,
    "curation_id": 2,
    "species_id": 1,
    "name": "Hippocampus Gene expression correlates of Open Field -Total distance in the perimeter in Females & Males BXD",
    "abbreviation": "HPC OF_TOT_PERIM_DIST_PCT F&M BXD M430v2 RMA",
    "publication_id": 104,
    "description": "Hippocampus Gene Expression Correlates for OF_TOT_PERIM_DIST_PCT measured in BXD RI Females & Males obtained using GeneNetwork Hippocampus Consortium M430v2 (Jun06) RMA. The OF_TOT_PERIM_DIST_PCT measures Open Field -Total distance in the perimeter under the domain Basal Behavior. The correlates were thresholded at a p-value of less than 0.001.",
    "count": 36,
    "score_type": 1,
    "threshold": "0.001",
    "status": "normal",
    "gene_id_type": 71,
    "attribution": '',
    "created": "2010-03-23",
    "updated": "2024-10-22T14:59:57.497457",
    publication_abstract: '',
    publication_authors: '',
    publication_journal: '',
    publication_month: '',
    publication_pages: '',
    publication_pubmed_id: '',
    publication_title: '',
    publication_volume: '',
    publication_year: ''
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        HomeComponent,
        SearchBarComponent,
        GeneSetListComponent,
      ],
      providers: [
        {provide: APIBaseService, useValue: mockAPIBaseService},
        {
          provide: ActivatedRoute,
          useValue: {
            queryParams: of({search: ''})
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(HomeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  describe('Initial State', () => {
    it('should initialize with default values', () => {
      expect(component.isSearchActive).toBeFalsy();
      expect(component.isLoading).toBeFalsy();
      expect(component.geneSets).toEqual([]);
      expect(component.searchValue).toBe('');
      expect(component.paging).toBeNull();
    });

    it('should display the GeneWeaver logo', () => {
      const logoElement = fixture.debugElement.query(By.css('img[src="geneweaver-logo.png"]'));
      expect(logoElement).toBeTruthy();
      expect(logoElement.nativeElement.className).toContain('spin-animation');
    });

    it('should display the GeneWeaver title', () => {
      const titleElement = fixture.debugElement.query(By.css('#title'));
      expect(titleElement).toBeTruthy();
      expect(titleElement.nativeElement.textContent.trim()).toBe('GeneWeaver');
    });
  });

  describe('Search Functionality', () => {
    it('should handle search execution', () => {
      component.onSearchExecuted();
      expect(component.isSearchActive).toBeTruthy();
      expect(component.isLoading).toBeTruthy();
    });

    it('should handle search completion', () => {
      const mockGeneSets: GeneSet[] = [
        mockGeneset
      ];

      component.onSearchCompleted(mockGeneSets);
      expect(component.geneSets).toEqual(mockGeneSets);
      expect(component.isLoading).toBeFalsy();
    });
  });

  describe('UI State Changes', () => {
    it('should adjust margin-top based on search state', () => {
      // Test initial state
      const initialContainer = fixture.debugElement.query(By.css('#home'));
      expect(initialContainer.styles['marginTop']).toBe('18vh');

      // Test after search activation
      component.isSearchActive = true;
      fixture.detectChanges();
      expect(initialContainer.styles['marginTop']).toBe('0px');
    });

    it('should show gene set list only when results exist', () => {
      // Initial state - no results
      let geneSetList = fixture.debugElement.query(By.css('#genesetResults'));
      expect(geneSetList).toBeNull();

      // After adding results
      component.geneSets = [
        mockGeneset
      ];
      fixture.detectChanges();
      geneSetList = fixture.debugElement.query(By.css('#genesetResults'));
      expect(geneSetList).toBeTruthy();
    });
  });

  describe('Style Classes', () => {
    it('should apply correct font family to title', () => {
      const titleElement = fixture.debugElement.query(By.css('.carrois-gothic-regular'));
      expect(titleElement).toBeTruthy();
    });

    it('should apply spin animation to logo', () => {
      const logoElement = fixture.debugElement.query(By.css('.spin-animation'));
      expect(logoElement).toBeTruthy();
    });
  });

  describe('Child Component Integration', () => {
    it('should include SearchBarComponent', () => {
      const searchBar = fixture.debugElement.query(By.directive(SearchBarComponent));
      expect(searchBar).toBeTruthy();
    });

    it('should include GeneSetListComponent when results exist', () => {
      component.geneSets = [
        mockGeneset
      ];
      fixture.detectChanges();

      const geneSetList = fixture.debugElement.query(By.directive(GeneSetListComponent));
      expect(geneSetList).toBeTruthy();
    });
  });

  describe('Responsive Layout', () => {
    it('should have responsive width classes', () => {
      const responsiveContainer = fixture.debugElement.query(By.css('.w-full.md\\:w-12.lg\\:w-10.xl\\:w-8.xxl\\:w-6.sm\\:w-full'));
      expect(responsiveContainer).toBeTruthy();
    });
  });
});