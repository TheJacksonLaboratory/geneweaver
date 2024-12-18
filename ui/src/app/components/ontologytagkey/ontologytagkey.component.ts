import {Component, Input, OnChanges, OnInit, SimpleChanges} from '@angular/core';
import { CommonModule } from '@angular/common';
import { TagModule } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';
import { OntologyTerm, ontologyColorMap } from "../../models/ontology-term"

interface SourceOntology {
  name: string;
  color: string;
}

@Component({
  selector: 'app-ontology-tag-key',
  standalone: true,
  imports: [CommonModule, TagModule, TooltipModule],
  templateUrl: './ontologytagkey.component.html',
  styleUrl: './ontologytagkey.component.css',
})
export class OntologyTagKeyComponent implements OnInit {
  @Input() ontology_terms: OntologyTerm[] = [];
  source_ontologies: SourceOntology[] = [];

  private fallbackColors = ["gray", "bluegray", "yellow", "teal", "pink", "indigo", "cyan"];

  private getColorForOntology(ontologyName: string, index: number): string {
    return ontologyColorMap[ontologyName] || this.fallbackColors[index % this.fallbackColors.length];
  }

  ngOnInit(): void {
    const uniqueOntologies = [...new Set(this.ontology_terms.map(term => term.source_ontology))];
    
    this.source_ontologies = uniqueOntologies.map((name, index) => ({
      name,
      color: this.getColorForOntology(name, index)
    }));
  }
}
