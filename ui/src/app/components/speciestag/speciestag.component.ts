import { Component, Input } from '@angular/core';
import { TagModule } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';

@Component({
  selector: 'app-speciestag',
  standalone: true,
  imports: [TooltipModule, TagModule],
  templateUrl: './speciestag.component.html',
  styleUrl: './speciestag.component.scss'
})
export class SpeciestagComponent {
  @Input() species_id = 0;

  /**
   * By species id (`SpeciesInt` in `geneweaver.core.enum`). These were lists read by
   * position, but the ids skip 7, so every species from 8 on was labelled as the next one
   * (C. elegans showed as yeast) and 11-13 had no entry. Unknown ids fall back to the id.
   */
  species: Record<number, { name: string; common: string; color: string }> = {
    0: { name: 'All', common: 'All', color: 'gray' },
    1: { name: 'Mus musculus', common: 'Mouse', color: 'bluegray' },
    2: { name: 'Homo sapiens', common: 'Human', color: 'yellow' },
    3: { name: 'Rattus norvegicus', common: 'Rat', color: 'green' },
    4: { name: 'Danio rerio', common: 'Zebrafish', color: 'red' },
    5: { name: 'Drosophila melanogaster', common: 'Fruit fly', color: 'purple' },
    6: { name: 'Macaca mulatta', common: 'Macaque', color: 'orange' },
    8: { name: 'Caenorhabditis elegans', common: 'Nematode', color: 'pink' },
    9: { name: 'Saccharomyces cerevisiae', common: 'Yeast', color: 'teal' },
    10: { name: 'Gallus gallus', common: 'Chicken', color: 'indigo' },
    11: { name: 'Canis familiaris', common: 'Dog', color: 'gray' },
    12: { name: 'Xenopus tropicalis', common: 'Western clawed frog', color: 'cyan' },
    13: { name: 'Xenopus laevis', common: 'African clawed frog', color: 'blue' },
  };

  getSpeciesName(): string {
    return this.species[this.species_id]?.name ?? `Species ${this.species_id}`;
  }

  getSpeciesCommonName(): string {
    return this.species[this.species_id]?.common ?? `Species ${this.species_id}`;
  }

  getSpeciesColor(): string {
    return this.species[this.species_id]?.color ?? 'gray';
  }
}
