import { Component, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
// The previous search bar, kept for reference; replaced by GenesetSearchComponent (G3-777, G3-764).
// import { SearchBarComponent } from "../../components/searchbar/searchbar.component";
import { GenesetSearchComponent } from "../../components/genesetsearch/geneset-search.component";
import { ButtonModule } from "primeng/button";
import { GeneSetListComponent } from "../../components/genesetlist/genesetlist.component";
import { Paging } from "jax-apiutils"
import { GeneSet } from "../../models/gene-set";
import { Router } from "@angular/router";

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, GenesetSearchComponent, GeneSetListComponent, ButtonModule],
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

  // @ViewChild(SearchBarComponent) searchBarComponent!: SearchBarComponent;
  @ViewChild(GenesetSearchComponent) searchField!: GenesetSearchComponent;

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
    // this.searchBarComponent.clearSearch();
    this.searchField.clear();
    this.isSpinning = true;

    setTimeout(() => {
      this.isSpinning = false; 
    }, 700);
  }
}
