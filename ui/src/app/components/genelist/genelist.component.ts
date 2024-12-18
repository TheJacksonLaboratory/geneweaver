import {Component, Input, OnInit} from '@angular/core';
import { CommonModule } from '@angular/common';
import { GeneValue, SimpleGeneValue } from '../../models/gene-value'
import { TableModule } from "primeng/table";
import { ApiBaseService, ApiBaseServiceFactory } from "jax-apiutils";
import {HttpParams} from "@angular/common/http";


@Component({
  selector: 'app-gene-list',
  standalone: true,
  imports: [CommonModule, TableModule],
  templateUrl: './genelist.component.html',
  styleUrl: './genelist.component.css',
})
export class GeneListComponent implements OnInit {
  private gwApi: ApiBaseService;

  @Input() geneset_id?: number;
  @Input() genes: GeneValue[] = [];
  @Input() mapped_genes: SimpleGeneValue[] = []

  constructor(
      private apiBaseServiceFactory: ApiBaseServiceFactory,
  ) {
    this.gwApi = this.apiBaseServiceFactory.create('https://geneweaver.jax.org/api')
  }

  ngOnInit(): void {
    this.fetchGeneValues();
  }

  private fetchGeneValues() {
    this.gwApi.getCollection<SimpleGeneValue>(`/genesets/${this.geneset_id}/values`, new HttpParams().set('gene_id_type', 'Gene Symbol')).subscribe(response => {
      this.mapped_genes = response.data;
    })
  }
}
