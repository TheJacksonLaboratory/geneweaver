import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { OntologyTagComponent } from "../ontologytag/ontologytag.component";
import { OntologyTerm } from "../../models/ontology-term"
import {OntologyTagKeyComponent} from "../ontologytagkey/ontologytagkey.component";

@Component({
  selector: 'app-ontology-annotations',
  standalone: true,
  imports: [CommonModule, OntologyTagComponent, OntologyTagKeyComponent],
  templateUrl: './ontologyannotations.component.html',
  styleUrl: './ontologyannotations.component.css',
})
export class OntologyAnnotationsComponent {
  @Input() ontology_tags: OntologyTerm[] = [];
}
