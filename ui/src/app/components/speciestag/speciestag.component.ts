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

  species_names = ["All", "Mus musculus", "Homo Sapiens", "Rattus norvegicus",
    "Danio rerio", "Drosophila Melanogaster", "Macaca mulatta", "Caenorhabditis elegans",
    "Saccharomyces cerevisiae", "Gallus gallus", "Xenopus tropicalis", "Xenopus laevis"];
  species_common_names = ["All", "Mouse", "Human", "Rat",
    "Zebrafish", "Fruit Fly", "Macaque", "Nematode",
    "Yeast", "Chicken", "Western clawed frog", "African clawed frog"];

  species_colors = ["gray", "bluegray", "yellow", "green", "red", "purple", "orange", "pink", "teal", "indigo", "cyan", "blue"];

  getSpeciesName(): string {
    return this.species_names[this.species_id];
  }

  getSpeciesCommonName(): string {
    return this.species_common_names[this.species_id];
  }

  getSpeciesColor(): string {
    return this.species_colors[this.species_id];
  }

}
