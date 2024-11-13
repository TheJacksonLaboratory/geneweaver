import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { TableModule } from "primeng/table";
import { TagModule } from "primeng/tag";
import { Button } from "primeng/button";
import { GeneSet } from "../../models/gene-set";
import { TierTagComponent } from "../tiertag/tiertag.component";
import { RippleModule } from 'primeng/ripple';

@Component({
  selector: 'app-gene-set-list',
  standalone: true,
  imports: [CommonModule, TableModule, TagModule, Button, TierTagComponent, RippleModule],
  templateUrl: './genesetlist.component.html',
  styleUrl: './genesetlist.component.scss',
})
export class GeneSetListComponent {
  @Input() geneSets: GeneSet[] = [];

  constructor(private router: Router) {
  }

  onGeneSetClick(geneSet: any) {
    // Handle click event
    // this.router.navigate(['/geneset', geneSet.id]);
    window.open('https://geneweaver.org/viewgenesetdetails/' + geneSet.id, '_blank');
  }
}
