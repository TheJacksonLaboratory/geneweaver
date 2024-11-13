import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GeneSetListComponent } from './genesetlist.component';
import { CommonModule } from '@angular/common';
import { TableModule } from "primeng/table";
import { TagModule } from "primeng/tag";
import { Button } from "primeng/button";
import { TierTagComponent } from "../tiertag/tiertag.component";
import { Router } from '@angular/router';
import { GeneSet } from "../../models/gene-set";


describe('GeneSetListComponent', () => {
  let component: GeneSetListComponent;
  let fixture: ComponentFixture<GeneSetListComponent>;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GeneSetListComponent, CommonModule, TableModule, TagModule, Button, TierTagComponent],
      providers: [
        { provide: Router, useValue: { navigate: jasmine.createSpy('navigate') } }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(GeneSetListComponent);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should display gene sets', () => {
    const geneSets: GeneSet[] = [
      {
        id: 1, name: 'Gene Set 1', count: 50, curation_id: 1, description: 'Description 1',
        abbreviation: '',
        attribution: '',
        created: '',
        file_id: 0,
        gene_id_type: 0,
        publication_abstract: '',
        publication_authors: '',
        publication_id: 0,
        publication_journal: '',
        publication_month: '',
        publication_pages: '',
        publication_pubmed_id: '',
        publication_title: '',
        publication_volume: '',
        publication_year: '',
        score_type: 0,
        species_id: 0,
        status: '',
        threshold: '',
        updated: '',
        user_id: 0
      },
      {
        id: 2, name: 'Gene Set 2', count: 75, curation_id: 2, description: 'Description 2',
        abbreviation: '',
        attribution: '',
        created: '',
        file_id: 0,
        gene_id_type: 0,
        publication_abstract: '',
        publication_authors: '',
        publication_id: 0,
        publication_journal: '',
        publication_month: '',
        publication_pages: '',
        publication_pubmed_id: '',
        publication_title: '',
        publication_volume: '',
        publication_year: '',
        score_type: 0,
        species_id: 0,
        status: '',
        threshold: '',
        updated: '',
        user_id: 0
      },
      {
        id: 3, name: 'Gene Set 3', count: 30, curation_id: 3, description: 'Description 3',
        abbreviation: '',
        attribution: '',
        created: '',
        file_id: 0,
        gene_id_type: 0,
        publication_abstract: '',
        publication_authors: '',
        publication_id: 0,
        publication_journal: '',
        publication_month: '',
        publication_pages: '',
        publication_pubmed_id: '',
        publication_title: '',
        publication_volume: '',
        publication_year: '',
        score_type: 0,
        species_id: 0,
        status: '',
        threshold: '',
        updated: '',
        user_id: 0
      }
    ];
    component.geneSets = geneSets;
    fixture.detectChanges();

    const tableRows = fixture.nativeElement.querySelectorAll('tr');
    expect(tableRows.length).toBe(4); // Header row + 3 data rows
    expect(tableRows[1].textContent).toContain('Gene Set 1');
    expect(tableRows[1].textContent).toContain('50');
    expect(tableRows[1].textContent).toContain('Tier 1');
  });

  it('should navigate to gene set details on click', () => {
    const geneSets: GeneSet[] = [
      {
        id: 1, name: 'Gene Set 1', count: 50, curation_id: 1, description: 'Description 1',
        abbreviation: '',
        attribution: '',
        created: '',
        file_id: 0,
        gene_id_type: 0,
        publication_abstract: '',
        publication_authors: '',
        publication_id: 0,
        publication_journal: '',
        publication_month: '',
        publication_pages: '',
        publication_pubmed_id: '',
        publication_title: '',
        publication_volume: '',
        publication_year: '',
        score_type: 0,
        species_id: 0,
        status: '',
        threshold: '',
        updated: '',
        user_id: 0
      }
    ];
    component.geneSets = geneSets;
    fixture.detectChanges();

    const firstRow = fixture.nativeElement.querySelector('tr:nth-child(2)');
    firstRow.click();
    expect(router.navigate).toHaveBeenCalledWith(['/geneset', 1]);
  });
});