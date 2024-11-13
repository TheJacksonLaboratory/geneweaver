import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import {TagModule} from "primeng/tag";

@Component({
  selector: 'app-tier-tag',
  standalone: true,
  imports: [CommonModule, TagModule],
  templateUrl: './tiertag.component.html',
  styleUrl: './tiertag.component.scss',
})
export class TierTagComponent {
  @Input() tier = 5;

  tierLabels = ['Tier I', 'Tier II', 'Tier III', 'Tier IV', 'Tier V'];
  tierColors = ['success', 'info', 'warning', 'danger', 'secondary'];

  getTierLabel(): string {
    return this.tierLabels[this.tier - 1];
  }

  getTierColor(): "success" | "secondary" | "info" | "warning" | "danger" | "contrast" {
    return this.tierColors[this.tier - 1] as "success" | "secondary" | "info" | "warning" | "danger" | "contrast";
  }
}
