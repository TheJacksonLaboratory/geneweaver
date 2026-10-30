import { NgFor } from '@angular/common';
import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';

/**
 * Picks between a tool's views (legacy offered several per tool, e.g. JaccardSimilarity's
 * Venn grid and its similarity matrix). Toggle buttons with `aria-pressed`, so the current
 * view is announced and every view is a Tab away.
 */
@Component({
  selector: 'app-view-switch',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgFor],
  template: `
    <div class="flex gap-1 mb-2" role="group" [attr.aria-label]="label">
      <button
        *ngFor="let option of options"
        type="button"
        class="p-button p-button-sm"
        [class.p-button-outlined]="option.id !== value"
        [attr.aria-pressed]="option.id === value"
        (click)="choose(option.id)"
      >
        {{ option.label }}
      </button>
    </div>
  `,
})
export class ViewSwitchComponent {
  @Input({ required: true }) options!: { id: string; label: string }[];
  @Input({ required: true }) value!: string;
  @Input() label = 'View';
  @Output() valueChange = new EventEmitter<string>();

  choose(id: string): void {
    if (id !== this.value) {
      this.value = id;
      this.valueChange.emit(id);
    }
  }
}
