import { Component, OnInit, inject, input, output, model } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GeneValue,  SimpleGeneValue, GeneIdTypes} from '../../models/gene-value';
import { TableModule } from "primeng/table";
import { SelectModule } from 'primeng/select';
import { ApiBaseService, ApiBaseServiceFactory } from "jax-apiutils";
import {HttpParams} from "@angular/common/http";
import { GeneSet } from '../../models/gene-set';
import { FormsModule } from '@angular/forms';

import { environment } from '../../../environments/environment';

interface IDType {
  name: string;
  code: string;
}

@Component({
  selector: 'app-gene-list',
  imports: [CommonModule, TableModule, SelectModule, FormsModule],
  templateUrl: './genelist.component.html',
  styleUrl: './genelist.component.css',
})
export class GeneListComponent implements OnInit {
  private apiBaseServiceFactory = inject(ApiBaseServiceFactory);

  private gwApi: ApiBaseService;
  geneset: any;

  readonly geneset_id = input<number>();
  /** Given by the parent, or fetched here for `geneset_id`. */
  readonly genes = model<GeneValue[]>([]);
  readonly mapped_genes = input<SimpleGeneValue[]>([]);
  readonly genesListChange = output<GeneValue[]>();

  idTypes: IDType[] | undefined;
  selectedIdType: IDType | undefined;
  constructor() {
    this.gwApi = this.apiBaseServiceFactory.create(environment.urls.geneWeaverApi)
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

    this.gwApi.getCollection<GeneSet>(`/genesets/${this.geneset_id()}`, new HttpParams().set('gene_id_type', idType)).subscribe(response => {
      this.geneset= response;
      this.genes.set(this.geneset.object.geneset_values as GeneValue[]);
      this.genesListChange.emit(this.genes());
    })
  }
}
