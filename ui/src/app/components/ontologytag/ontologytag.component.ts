import { Component, OnChanges, SimpleChanges, input } from '@angular/core';

import { TagModule } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';
import { OntologyTerm, ontologyColorMap } from "../../models/ontology-term"

@Component({
  selector: 'app-ontology-tag',
  imports: [TagModule, TooltipModule],
  templateUrl: './ontologytag.component.html',
  styleUrl: './ontologytag.component.css',
})
export class OntologyTagComponent implements OnChanges {
  readonly ontology = input<OntologyTerm | null>(null);

  getOntologyColor(): string {
    return this.getColorForOntology(this.ontology()?.source_ontology || '', 0);
  }

  ontology_string = '';

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  ngOnChanges(_changes: SimpleChanges): void {
    const ontology = this.ontology();
    this.ontology_string = ontology?.name + " (" + ontology?.ontology_term_id + ")"
  }

  private fallbackColors = ["gray", "bluegray", "yellow", "teal", "pink", "indigo", "cyan"];

  private getColorForOntology(ontologyName: string, index: number): string {
    return ontologyColorMap[ontologyName] || this.fallbackColors[index % this.fallbackColors.length];
  }

}
