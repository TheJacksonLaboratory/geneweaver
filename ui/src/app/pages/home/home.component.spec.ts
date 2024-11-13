import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HomeComponent } from './home.component';
import { SearchBarComponent } from "../../components/searchbar/searchbar.component";
import { GeneSetListComponent } from "../../components/genesetlist/genesetlist.component";
import { Paging } from "../../jaxapiutils/models/api-interfaces";
import { GeneSet } from "../../models/gene-set";
import { By } from '@angular/platform-browser';
import { provideHttpClientTesting } from '@angular/common/http/testing';

describe('HomeComponent', () => {
  let component: HomeComponent;
  let fixture: ComponentFixture<HomeComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        HomeComponent,
        SearchBarComponent,
        GeneSetListComponent,
      ],
      providers: [provideHttpClientTesting()]
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
      const titleElement = fixture.debugElement.query(By.css('#geneweaver'));
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
        // Add mock GeneSet objects here based on your GeneSet interface
      ];

      component.onSearchCompleted(mockGeneSets);
      expect(component.geneSets).toEqual(mockGeneSets);
      expect(component.isLoading).toBeFalsy();
    });

    it('should handle search paging', () => {
      const mockPaging: Paging = {
        // Add mock Paging object here based on your Paging interface
      };

      component.onSearchPaging(mockPaging);
      expect(component.paging).toEqual(mockPaging);
    });
  });

  describe('UI State Changes', () => {
    it('should adjust margin-top based on search state', () => {
      // Test initial state
      const initialContainer = fixture.debugElement.query(By.css('.block'));
      expect(initialContainer.styles['margintop']).toBe('18vh');

      // Test after search activation
      component.isSearchActive = true;
      fixture.detectChanges();
      expect(initialContainer.styles['margintop']).toBe('0');
    });

    it('should show gene set list only when results exist', () => {
      // Initial state - no results
      let geneSetList = fixture.debugElement.query(By.css('[*ngif="geneSets.length > 0"]'));
      expect(geneSetList).toBeNull();

      // After adding results
      component.geneSets = [
        // Add mock GeneSet objects here
      ];
      fixture.detectChanges();
      geneSetList = fixture.debugElement.query(By.css('[*ngif="geneSets.length > 0"]'));
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
        // Add mock GeneSet objects here
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