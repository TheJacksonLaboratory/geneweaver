import {Component, OnInit} from '@angular/core';
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
import { GeneValueDownload } from '../../models/gene-value';
import { convertModel} from '../../utils/utils';
import { Router } from '@angular/router';

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
export class GeneSetComponent implements OnInit {
  private gwApi: ApiBaseService;
  pubmedUrl: string = environment.urls.pubmed + '/';
  genesetDetails: any;
  geneset: any;
  geneset_values: any[] = [];
  publication: any;
  has_publication = false;
  score_type = '';
  threshold_string = '';
  genesInThreshold: GeneValue[] = [];
  displayGenesInThreshold = ""

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
    private apiBaseServiceFactory: ApiBaseServiceFactory,
    private router: Router
  ) {
    this.gwApi = this.apiBaseServiceFactory.create(
      'https://geneweaver.jax.org/api'
    );
  }

  ngOnInit(): void {
    this.route.params.subscribe((params) => {
      const genesetId = params['id'];
      this.fetchGenesetDetails(genesetId);
      this.fetchPublicationDetails(genesetId);
      this.fetchOntologyDetails(genesetId);
      this.fetchGenesetValuesInThreshold(genesetId);
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

  private fetchGenesetValuesInThreshold(genesetId: string) {
    /**
     * Fetch geneset values in threshold
     * Sets the genesInThreshold array with the response data
     * and sets the displayGenesInThreshold string with the length of the array
     */
    this.gwApi
      .getCollection<GeneValue>(
        `/genesets/${genesetId}/values`,
        new HttpParams().set('in_threshold', true)
      )
      .subscribe({
        next: (response) => {
          this.genesInThreshold = response.data;
          if (this.genesInThreshold.length > 0) {
            this.displayGenesInThreshold = "| (genes in threshold: " + this.genesInThreshold.length + ")";
          }
        },
        error: (error) => {
          console.error('Error fetching geneset values:', error);
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
    const downloadData: GeneValueDownload[] = this.geneset_values.map(gene => convertModel<GeneValue, GeneValueDownload>(gene, GeneValueDownload));
    downloadData.forEach((gene) => {
      gene.gsv_source_list = gene.gsv_source_list.join(',');
    });
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
        'gsv_source_list',
        'gsv_value',
        'ode_ref_id'
      ],
    };
    new ngxCsv(
       downloadData,
      'geneweaver-genes-GS-' + this.geneset.id + '-' + dateString,
      options
    );
  }

  private downloadJson() {
    /* Download the JSON file
     *  Creates an objectURL for the JSON file and triggers a download
     *  using the anchor element
     * */

    const downloadData: GeneValueDownload[] = this.geneset_values.map(gene => convertModel<GeneValue, GeneValueDownload>(gene, GeneValueDownload));
    const date = new Date();
    const dateString = date.toISOString().slice(0, 10);
    // set the objectURL for the JSON file
    const theJSON = JSON.stringify(downloadData);
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

  searchGenesetsForPublication(searchTerm: string) {
    this.router.navigate(['/search'], {
      queryParams: { search: searchTerm }
    });
  }
}
