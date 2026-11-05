import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { TableModule } from "primeng/table";
import { TagModule } from "primeng/tag";
import { Button } from "primeng/button";
import { GeneSet } from "../../models/gene-set";
import { TierTagComponent } from "../tiertag/tiertag.component";
import { RippleModule } from 'primeng/ripple';
import { scoreTypeName, Sort, SortKey, speciesName } from '../../search/search-filters';

/** The sortable columns, in the table's order (G3-777). */
export const SORTABLE_COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'id', label: 'ID' },
  { key: 'name', label: 'Name' },
  { key: 'species', label: 'Species' },
  { key: 'size', label: 'Size' },
  { key: 'tier', label: 'Tier' },
  { key: 'score_type', label: 'Score' },
];

@Component({
  selector: 'app-gene-set-list',
  standalone: true,
  imports: [CommonModule, TableModule, TagModule, Button, TierTagComponent, RippleModule],
  templateUrl: './genesetlist.component.html',
  styleUrl: './genesetlist.component.scss',
})
export class GeneSetListComponent {
  @Input() geneSets: GeneSet[] = [];
  /** The order the results are in, to mark the sorted column. */
  @Input() sort: Sort = { by: null, order: 'asc' };
  /**
   * A header was clicked. Sorting is the search's to do (G3-777): results arrive a page at a
   * time, so sorting the rows on screen would sort only the first page.
   */
  @Output() sortChange = new EventEmitter<Sort>();

  readonly columns = SORTABLE_COLUMNS;
  readonly speciesName = speciesName;
  readonly scoreTypeName = scoreTypeName;

  constructor(private router: Router) {
  }

  /** The first click sorts ascending, the next descending, the next clears the sort. */
  toggleSort(key: SortKey): void {
    if (this.sort.by !== key) {
      this.sortChange.emit({ by: key, order: 'asc' });
    } else if (this.sort.order === 'asc') {
      this.sortChange.emit({ by: key, order: 'desc' });
    } else {
      this.sortChange.emit({ by: null, order: 'asc' });
    }
  }

  sortIcon(key: SortKey): string {
    if (this.sort.by !== key) {
      return 'pi pi-sort-alt';
    }
    return this.sort.order === 'asc' ? 'pi pi-sort-amount-up-alt' : 'pi pi-sort-amount-down';
  }

  ariaSort(key: SortKey): string | null {
    if (this.sort.by !== key) {
      return null;
    }
    return this.sort.order === 'asc' ? 'ascending' : 'descending';
  }

  onGeneSetClick(geneSet: any) {
    // Handle click event
    this.router.navigate(['/geneset', geneSet.id]);
    // window.open('https://geneweaver.org/viewgenesetdetails/' + geneSet.id, '_blank');
  }
}
