import { Component, inject, input, output } from '@angular/core';

import { Router } from '@angular/router';
import { TableModule } from "primeng/table";
import { TagModule } from "primeng/tag";
import { Button } from "primeng/button";
import { GeneSet } from "../../models/gene-set";
import { TierTagComponent } from "../tiertag/tiertag.component";
import { RippleModule } from 'primeng/ripple';
import {
  describeMatches,
  scoreTypeName,
  Sort,
  SortKey,
  speciesName,
} from '../../search/search-filters';

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
  imports: [TableModule, TagModule, Button, TierTagComponent, RippleModule],
  templateUrl: './genesetlist.component.html',
  styleUrl: './genesetlist.component.scss',
})
export class GeneSetListComponent {
  private router = inject(Router);

  readonly geneSets = input<GeneSet[]>([]);
  /** The order the results are in, to mark the sorted column. */
  readonly sort = input<Sort>({ by: null, order: 'asc' });
  /**
   * A header was clicked. Sorting is the search's to do (G3-777): results arrive a page at a
   * time, so sorting the rows on screen would sort only the first page.
   */
  readonly sortChange = output<Sort>();

  readonly columns = SORTABLE_COLUMNS;
  readonly speciesName = speciesName;
  readonly scoreTypeName = scoreTypeName;
  /** Which gene each result matched in a gene search, e.g. "dop-3 (homolog of Drd2)". */
  readonly describeMatches = describeMatches;

  /** The first click sorts ascending, the next descending, the next clears the sort. */
  toggleSort(key: SortKey): void {
    const sort = this.sort();
    if (sort.by !== key) {
      this.sortChange.emit({ by: key, order: 'asc' });
    } else if (sort.order === 'asc') {
      this.sortChange.emit({ by: key, order: 'desc' });
    } else {
      this.sortChange.emit({ by: null, order: 'asc' });
    }
  }

  sortIcon(key: SortKey): string {
    const sort = this.sort();
    if (sort.by !== key) {
      return 'pi pi-sort-alt';
    }
    return sort.order === 'asc' ? 'pi pi-sort-amount-up-alt' : 'pi pi-sort-amount-down';
  }

  ariaSort(key: SortKey): string | null {
    const sort = this.sort();
    if (sort.by !== key) {
      return null;
    }
    return sort.order === 'asc' ? 'ascending' : 'descending';
  }

  onGeneSetClick(geneSet: any) {
    // Handle click event
    this.router.navigate(['/geneset', geneSet.id]);
    // window.open('https://geneweaver.org/viewgenesetdetails/' + geneSet.id, '_blank');
  }
}
