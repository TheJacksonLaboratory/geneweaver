import {Component, Input, OnInit} from '@angular/core';
import { CommonModule } from '@angular/common';
import { GeneValue,  SimpleGeneValue, GeneIdTypes} from '../../models/gene-value';
import { TableModule } from "primeng/table";
import { DropdownModule } from 'primeng/dropdown';
import { ApiBaseService, ApiBaseServiceFactory } from "jax-apiutils";
import {HttpParams} from "@angular/common/http";
import { GeneSet } from '../../models/gene-set';
import { FormsModule } from '@angular/forms';

interface IDType {
  name: string;
  code: string;
}

@Component({
  selector: 'app-gene-list',
  standalone: true,
  imports: [CommonModule, TableModule, DropdownModule, FormsModule],
  templateUrl: './genelist.component.html',
  styleUrl: './genelist.component.css',
})
export class GeneListComponent implements OnInit {
  private gwApi: ApiBaseService;
  geneset: any;

  @Input() geneset_id?: number;
  @Input() genes: GeneValue[] = [];
  @Input() mapped_genes: SimpleGeneValue[] = []


  idTypes: IDType[] | undefined;
  selectedIdType: IDType | undefined;
  constructor(
      private apiBaseServiceFactory: ApiBaseServiceFactory
  ) {
    this.gwApi = this.apiBaseServiceFactory.create('https://geneweaver.jax.org/api')
  }

  ngOnInit(): void {
    /* Initialize the gene list component */

    this.selectedIdType = { name: GeneIdTypes.GENE_SYMBOL.toUpperCase(), code: GeneIdTypes.GENE_SYMBOL };

    this.idTypes = [];
    for (const key in GeneIdTypes) {
      const idTypeCode: string = GeneIdTypes[key as keyof typeof GeneIdTypes];
      const idTypeName: string = idTypeCode.toUpperCase()
      this.idTypes.push({ name: idTypeName, code: idTypeCode });
    }

    this.fetchGeneValues();
  }

  fetchGeneValues(idType: string = GeneIdTypes.GENE_SYMBOL) {
    /* Fetch the gene values for the given gene set */

    this.gwApi.getCollection<GeneSet>(`/genesets/${this.geneset_id}`, new HttpParams().set('gene_id_type', idType)).subscribe(response => {
      this.geneset= response;
      this.genes = this.geneset.object.geneset_values;
    })
  }
}
