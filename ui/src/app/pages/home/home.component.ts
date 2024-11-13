import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SearchBarComponent } from "../../components/searchbar/searchbar.component";
import { GeneSetListComponent } from "../../components/genesetlist/genesetlist.component";
import { Paging } from "../../jaxapiutils/models/api-interfaces";
import { GeneSet } from "../../models/gene-set";

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

  onSearchExecuted() {
    this.isSearchActive = true;
    this.isLoading = true;
    console.log("Search executed");
  }

  onSearchCompleted(geneSets: GeneSet[]) {
    this.geneSets = geneSets;
    this.isLoading = false;
  }

  onSearchPaging(paging: Paging) {
    this.paging = paging;
  }
}
