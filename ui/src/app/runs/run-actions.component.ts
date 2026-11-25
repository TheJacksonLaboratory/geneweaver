import { Component, computed, input, output } from '@angular/core';
import { MenuItem } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { MenuModule } from 'primeng/menu';

import { downloadUrl, runDownloads } from './tool-runs';

/**
 * Download and rerun for one stored run (G3-840).
 *
 * Downloads are links to the API, which builds each file from the stored result
 * (`/tools/runs/{id}/download`) and names it; nothing is rebuilt here.
 */
@Component({
  selector: 'app-run-actions',
  imports: [ButtonModule, MenuModule],
  // Inline, so the actions sit on one line beside a row's other buttons.
  host: { class: 'inline-block' },
  template: `
    <div class="inline-flex flex-wrap align-items-center gap-2 run-actions">
      <p-menu #downloads [model]="downloadItems()" [popup]="true" appendTo="body" />
      <p-button
        label="Download"
        icon="pi pi-download"
        size="small"
        [outlined]="true"
        ariaLabel="Download this result"
        (onClick)="downloads.toggle($event)"
      />
      @if (canRerun()) {
        <p-button
          label="Rerun"
          icon="pi pi-refresh"
          size="small"
          severity="secondary"
          [outlined]="true"
          [disabled]="rerunning()"
          ariaLabel="Run this analysis again"
          (onClick)="rerun.emit()"
        />
      }
      @if (showRunId()) {
        <small class="text-color-secondary run-id">Run {{ runId() }}</small>
      }
    </div>
  `,
})
export class RunActionsComponent {
  readonly runId = input.required<number>();
  readonly tool = input<string | null | undefined>();
  readonly canRerun = input(true);
  /** Whether to name the run; a list row already does. */
  readonly showRunId = input(true);
  /** While a rerun this component asked for is being submitted. */
  readonly rerunning = input(false);
  readonly rerun = output<void>();

  readonly downloadItems = computed<MenuItem[]>(() =>
    runDownloads(this.tool()).map((download) => ({
      label: download.label,
      url: downloadUrl(this.runId(), download),
    })),
  );
}
