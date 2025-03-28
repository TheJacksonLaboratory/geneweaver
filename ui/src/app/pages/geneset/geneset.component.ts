import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { ApiBaseService, ApiBaseServiceFactory } from 'jax-apiutils';
import { SpeciestagComponent } from '../../components/speciestag/speciestag.component';
import { TierTagComponent } from '../../components/tiertag/tiertag.component';
import { GeneListComponent } from '../../components/genelist/genelist.component';

import { DividerModule } from 'primeng/divider';
import { SkeletonModule } from 'primeng/skeleton';
import { PanelModule } from 'primeng/panel';
import { MenubarModule } from 'primeng/menubar';
import { MenuItem } from 'primeng/api';
import { TableModule } from 'primeng/table';
import { DropdownModule } from 'primeng/dropdown';
import { CheckboxModule } from 'primeng/checkbox';
import { OntologyAnnotationsComponent } from '../../components/ontologyannotations/ontologyannotations.component';
import { OntologyTerm } from '../../models/ontology-term';
import { HttpParams } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { ngxCsv } from 'ngx-csv/ngx-csv';
import { MenuModule } from 'primeng/menu';
import { ButtonModule } from 'primeng/button';
import { GeneValue } from '../../models/gene-value';

@Component({
  selector: 'app-gene-set',
  standalone: true,
  imports: [
    CommonModule,
    SpeciestagComponent,
    TierTagComponent,
    GeneListComponent,
    DividerModule,
    SkeletonModule,
    PanelModule,
    MenubarModule,
    TableModule,
    DropdownModule,
    CheckboxModule,
    MenubarModule,
    OntologyAnnotationsComponent,
    MenuModule,
    ButtonModule,
  ],
  templateUrl: './geneset.component.html',
  styleUrl: './geneset.component.css',
})
export class GeneSetComponent {
  private gwApi: ApiBaseService;
  pubmedUrl: string = environment.urls.pubmed + '/';
  genesetDetails: any;
  geneset: any;
  geneset_values: any[] = [];
  publication: any;
  has_publication = false;
  score_type = '';
  threshold_string = '';

  score_type_map: { [key: number]: string } = {
    1: 'P-Value',
    2: 'Q-Value',
    3: 'Binary',
    4: 'Correlation',
    5: 'Effect',
  };

  ontologies: OntologyTerm[] = [];

  menuItems: MenuItem[] = [
    {
      label: 'Legacy Page',
      icon: 'pi pi-history',
      styleClass: 'p-button-secondary',
      command: () => this.onLegacyClick(this.geneset),
    },
  ];

  configMenuItems: MenuItem[] = [
    {
      id: 'download-json',
      label: 'Download JSON',
      icon: 'pi pi-download',
      command: () => {
        this.downloadJson();
      },
      disabled: true,
    },
    {
      id: 'download-csv',
      label: 'Download CSV',
      icon: 'pi pi-download',
      command: () => {
        this.downloadCsv();
      },
      disabled: true,
    },
  ];

  constructor(
    private route: ActivatedRoute,
    private apiBaseServiceFactory: ApiBaseServiceFactory
  ) {
    this.gwApi = this.apiBaseServiceFactory.create(
      'https://geneweaver.jax.org/api'
    );
  }

  ngOnInit() {
    this.route.params.subscribe((params) => {
      const genesetId = params['id'];
      this.fetchGenesetDetails(genesetId);
      this.fetchPublicationDetails(genesetId);
      this.fetchOntologyDetails(genesetId);
    });
  }

  private formatScoreType(score_type_int: number): string {
    return this.score_type_map[score_type_int];
  }

  private formatThreshold(score_type_int: number, threshold: number): string {
    if (score_type_int == 1) {
      return `p < ${threshold}`;
    } else if (score_type_int == 2) {
      return `q > ${threshold}`;
    } else if (score_type_int == 4 || score_type_int == 5) {
      const [first, second] = threshold.toString().split(',');
      return `${first} < ${second}`;
    } else {
      return '';
    }
  }

  private fetchGenesetDetails(genesetId: string) {
    this.gwApi.get(`/genesets/${genesetId}`).subscribe({
      next: (response) => {
        this.genesetDetails = response.object;
        this.geneset = this.genesetDetails.geneset;
        this.geneset_values = this.genesetDetails.geneset_values;
        this.score_type = this.formatScoreType(this.geneset.score_type);
        this.threshold_string = this.formatThreshold(
          this.geneset.score_type,
          this.geneset.threshold
        );
        if (this.geneset_values.length > 0) {
          this.configMenuItems[0].disabled = false;
          this.configMenuItems[1].disabled = false;
        }
      },
      error: (error) => {
        console.error('Error fetching geneset details:', error);
        // Handle error appropriately
      },
    });
  }

  private fetchPublicationDetails(genesetId: string) {
    this.gwApi.get(`/genesets/${genesetId}/publication`).subscribe({
      next: (response) => {
        this.publication = response.object;
        this.has_publication = true;
      },
      error: (error) => {
        this.publication = null;

        // Only set has_publication to false if it's a 404 error
        if (error.status === 404) {
          this.has_publication = false;
        } else {
          console.error('Error fetching publication details:', error);
        }
      },
    });
  }

  private fetchOntologyDetails(genesetId: string) {
    this.gwApi
      .getCollection<OntologyTerm>(
        `/genesets/${genesetId}/ontologies`,
        new HttpParams().set('limit', 100)
      )
      .subscribe({
        next: (response) => {
          console.log(response);
          this.ontologies = response.data;
        },
        error: (error) => {
          this.publication = null;

          // Only set has_publication to false if it's a 404 error
          if (error.status === 404) {
            this.has_publication = false;
          } else {
            console.error('Error fetching publication details:', error);
          }
        },
      });
  }

  onLegacyClick(geneSet: any) {
    // Handle click event
    // this.router.navigate(['/geneset', geneSet.id]);
    window.open(
      'https://geneweaver.org/viewgenesetdetails/' + geneSet.id,
      '_blank'
    );
  }

  private downloadCsv() {
    /**
     * Download the CSV file
     * Sets the options for the CSV file and triggers the download
     */

    const date = new Date();
    const dateString = date.toISOString().slice(0, 10);
    const options = {
      fieldSeparator: ',',
      quoteStrings: '"',
      decimalseparator: '.',
      showLabels: true,
      showTitle: false,
      title: 'Genes in Geneset',
      useBom: true,
      noDownload: false,
      headers: [
        'gs_id',
        'ode_gene_id',
        'gsv_value',
        'gsv_hits',
        'gsv_source_list',
        'gsv_value_list',
        'gsv_in_threshold',
        'gsv_date',
        'hom_id',
        'gene_rank',
        'ode_ref_id',
        'gdb_id',
      ],
    };
    const csv = new ngxCsv(
      this.geneset_values,
      'geneweaver-genes-GS-' + this.geneset.id + '-' + dateString,
      options
    );
  }

  private downloadJson() {
    /* Download the JSON file
     *  Creates an objectURL for the JSON file and triggers a download
     *  using the anchor element
     * */
    const date = new Date();
    const dateString = date.toISOString().slice(0, 10);
    // set the objectURL for the JSON file
    const theJSON = JSON.stringify(this.geneset_values);
    const blob = new Blob([theJSON], { type: 'text/json' });
    const link = document.createElement('a');
    const url = window.URL.createObjectURL(blob);

    // trigger the download with the anchor element
    link.href = url;
    link.download = 'geneweaver-genes-GS' + this.geneset.id + '-' + dateString + '.json';
    link.click();
    URL.revokeObjectURL(link.href);
  }

  onGeneListChange(genes: GeneValue[]) {
    // Handle gene list change from child component
    this.geneset_values = genes;
  }
}
