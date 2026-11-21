/* Angular Imports */
import { Component, OnInit, inject, output, model } from '@angular/core';

import { Router, ActivatedRoute } from '@angular/router';
import { HttpParams } from '@angular/common/http';
import { FormsModule } from "@angular/forms";
/* Jax API Utils Imports */
import { ApiBaseService, ApiBaseServiceFactory, Paging } from "jax-apiutils";

/* PrimeNG Imports */
import { MessageService } from 'primeng/api';
import { ToastModule } from "primeng/toast";
import { ProgressBarModule } from "primeng/progressbar";
import { ButtonModule } from "primeng/button";
import { InputTextModule } from "primeng/inputtext";
import { InputGroupModule } from 'primeng/inputgroup';

/* Local Imports */
import { GeneSet } from "../../models/gene-set";
import { environment } from "../../../environments/environment";


@Component({
  selector: 'app-search-bar',
  standalone: true,
  imports: [FormsModule, ToastModule, InputTextModule, InputGroupModule, ButtonModule, ProgressBarModule],
  providers: [MessageService],
  templateUrl: './searchbar.component.html',
  styleUrl: './searchbar.component.scss',
})
export class SearchBarComponent implements OnInit {
  private messageService = inject(MessageService);
  private apiBaseServiceFactory = inject(ApiBaseServiceFactory);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  isSearching = false;
  private gwApi: ApiBaseService;

  /** Two-way with the search box; set from the URL's `search` parameter. */
  readonly searchValue = model('');
  readonly searchExecuted = output<string>();
  readonly searchCompleted = output<GeneSet[]>();
  /** The response's paging; undefined when a response has none. */
  readonly searchPaging = output<Paging | undefined>();
  readonly searchCleared = output<boolean>();

  constructor() {
    this.gwApi = this.apiBaseServiceFactory.create(environment.urls.geneWeaverApi)
  }

  ngOnInit() {
    this.route.queryParams.subscribe(params => {
      if (params['search']) {
        this.searchValue.set(params['search']);
        this.onSearch(this.searchValue());
      } else {
        this.clearSearch();
      }
    });
  }

  clearSearch() {
    this.searchValue.set('');
    this.searchCleared.emit(true);
    this.searchCompleted.emit([]);
  }

  onSearch(searchTerm: string) {
    if (searchTerm) {
      this.isSearching = true;
      this.searchExecuted.emit(searchTerm);
      this.router.navigate([], {
        queryParams: { search: searchTerm },
        queryParamsHandling: 'merge'
      });
      this.gwApi
          .getCollection<GeneSet>('/genesets/search', new HttpParams().set('search_text', searchTerm))
          .subscribe((geneSets) => {
        this.isSearching = false;
        this.searchCompleted.emit(geneSets.data);
        this.searchPaging.emit(geneSets.paging);
      });

    } else {
      this.messageService.add({
        severity:'warn',
        summary: 'Search Term Required',
        detail: 'Please enter a search term before submitting a search.'
      });
    }
  }

}
