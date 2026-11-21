import { Component, input } from '@angular/core';

import { OntologyTagComponent } from "../ontologytag/ontologytag.component";
import { OntologyTerm } from "../../models/ontology-term"
import {OntologyTagKeyComponent} from "../ontologytagkey/ontologytagkey.component";

@Component({
  selector: 'app-ontology-annotations',
  imports: [OntologyTagComponent, OntologyTagKeyComponent],
  templateUrl: './ontologyannotations.component.html',
  styleUrl: './ontologyannotations.component.css',
})
export class OntologyAnnotationsComponent {
  readonly ontology_tags = input<OntologyTerm[]>([]);
}
