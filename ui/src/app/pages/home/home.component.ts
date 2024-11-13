import { Component, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SearchBarComponent } from "../../components/searchbar/searchbar.component";
import { GeneSetListComponent } from "../../components/genesetlist/genesetlist.component";
import { Paging } from "../../jaxapiutils/models/api-interfaces";
import { GeneSet } from "../../models/gene-set";
import { Router } from "@angular/router";

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, SearchBarComponent, GeneSetListComponent],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
})
export class HomeComponent {
  isSearchActive = false;
  isLoading = false;
  geneSets: GeneSet[] = [];
  searchValue = '';
  paging: Paging | null = null;
  isSpinning = true;

  @ViewChild(SearchBarComponent) searchBarComponent!: SearchBarComponent;

  constructor(private router: Router) {
    setTimeout(() => {
      this.isSpinning = false;
    }, 700);
  }

  onSearchExecuted() {
    this.isSearchActive = true;
    this.isLoading = true;
  }

  onSearchCompleted(geneSets: GeneSet[]) {
    this.geneSets = geneSets;
    this.isLoading = false;
  }

  onSearchPaging(paging: Paging) {
    this.paging = paging;
  }

  onLogoClick() {
    this.router.navigate(['/']);
    this.isSearchActive = false;
    this.searchValue = '';
    this.geneSets = [];
    this.paging = null;
    this.searchBarComponent.clearSearch();
    this.isSpinning = true;

    setTimeout(() => {
      this.isSpinning = false; 
    }, 700);
  }
}
