import { Component, Input } from '@angular/core';
import { TooltipModule } from 'primeng/tooltip';

/**
 * An info icon that explains the control beside it in a tooltip. The tooltip opens on hover
 * and on keyboard focus, and screen readers read the same text from the icon's label, so the
 * explanation does not depend on a mouse.
 */
@Component({
  selector: 'app-info-tip',
  standalone: true,
  imports: [TooltipModule],
  template: `
    <span
      class="info-tip pi pi-info-circle"
      tabindex="0"
      role="img"
      [attr.aria-label]="label ? label + ': ' + text : text"
      [pTooltip]="text"
      tooltipEvent="both"
      tooltipPosition="top"
      tooltipStyleClass="info-tip-tooltip"
      appendTo="body"
    ></span>
  `,
  styles: [
    `
      .info-tip {
        margin-left: 0.35rem;
        font-size: 0.8rem;
        color: var(--text-color-secondary);
        cursor: help;
        vertical-align: middle;
      }
      .info-tip:hover {
        color: var(--primary-color);
      }
      .info-tip:focus {
        outline: none;
      }
      .info-tip:focus-visible {
        outline: 2px solid var(--primary-color);
        outline-offset: 2px;
        border-radius: 50%;
      }
    `,
  ],
})
export class InfoTipComponent {
  /** What the tooltip says. */
  @Input({ required: true }) text = '';
  /** The control it explains, so a screen reader announces "Species: Only gene sets ...". */
  @Input() label = '';
}
