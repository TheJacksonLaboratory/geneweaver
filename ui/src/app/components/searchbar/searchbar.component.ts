/* Angular Imports */
import { Component, EventEmitter, Output, Input, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import { HttpParams } from '@angular/common/http';
import { FormsModule } from "@angular/forms";
/* Jax API Utils Imports */
import { APIBaseService } from '../../jaxapiutils/services/api-base.service';
import { Paging } from '../../jaxapiutils/models/api-interfaces';
/* PrimeNG Imports */
import { MessageService } from 'primeng/api';
import { ToastModule } from "primeng/toast";
import { ProgressBarModule } from "primeng/progressbar";
import { ButtonModule } from "primeng/button";
import { InputTextModule } from "primeng/inputtext";
import { InputGroupModule } from 'primeng/inputgroup';

/* Local Imports */
import { GeneSet } from "../../models/gene-set";


@Component({
  selector: 'app-search-bar',
  standalone: true,
  imports: [CommonModule, FormsModule, ToastModule, InputTextModule, InputGroupModule, ButtonModule, ProgressBarModule],
  providers: [MessageService],
  templateUrl: './searchbar.component.html',
  styleUrl: './searchbar.component.scss',
})
export class SearchBarComponent implements OnInit {
  isSearching = false;

  @Input() searchValue = '';
  @Output() searchExecuted = new EventEmitter<string>();
  @Output() searchCompleted = new EventEmitter<GeneSet[]>();
  @Output() searchPaging = new EventEmitter<Paging>();
  @Output() searchCleared = new EventEmitter<boolean>();

  constructor(
      private messageService: MessageService,
      private apiService: APIBaseService,
      private router: Router,
      private route: ActivatedRoute
  ) {}

  ngOnInit() {
    this.route.queryParams.subscribe(params => {
      if (params['search']) {
        this.searchValue = params['search'];
        this.onSearch(this.searchValue);
      } else {
        this.clearSearch();
      }
    });
  }

  clearSearch() {
    this.searchValue = '';
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
      this.apiService
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
