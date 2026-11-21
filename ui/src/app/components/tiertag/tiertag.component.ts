import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';

import {TagModule} from "primeng/tag";

@Component({
  selector: 'app-tier-tag',
  imports: [TagModule],
  templateUrl: './tiertag.component.html',
  styleUrl: './tiertag.component.scss',
})
export class TierTagComponent implements OnChanges {
  @Input() tier = 5;

  tierLabels = ['Tier I', 'Tier II', 'Tier III', 'Tier IV', 'Tier V'];
  tierColors = ['success', 'info', 'warn', 'danger', 'secondary'];

  public tierColor: "success" | "secondary" | "info" | "warn" | "danger" | "contrast" = "success";
  public tierLabel = '';

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['tier']) {
      this.tierLabel = this.getTierLabel();
      this.tierColor = this.getTierColor();
    }
  }

  getTierLabel(): string {
    return this.tierLabels[this.tier - 1];
  }

  getTierColor(): "success" | "secondary" | "info" | "warn" | "danger" | "contrast" {
    return this.tierColors[this.tier - 1] as "success" | "secondary" | "info" | "warn" | "danger" | "contrast";
  }
}
