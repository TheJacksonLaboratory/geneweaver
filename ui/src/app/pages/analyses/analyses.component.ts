import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { HttpParams } from '@angular/common/http';
import { Router, RouterLink } from '@angular/router';
import { ApiBaseService, ApiBaseServiceFactory } from 'jax-apiutils';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { MessageModule } from 'primeng/message';
import { TableLazyLoadEvent, TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';

import { environment } from '../../../environments/environment';
import { SessionService } from '../../services/session.service';
import { RunActionsComponent } from '../../runs/run-actions.component';
import {
  describeRunError,
  HttpFailure,
  toolLabel,
  ToolRunList,
  ToolRunSummary,
} from '../../runs/tool-runs';
import { renderAfter } from '../../utils/render-after';

/** How many runs a page of the list shows. */
export const RUNS_PER_PAGE = 25;

/** The tag a run's status shows as. */
export function statusTag(run: ToolRunSummary): { value: string; severity: 'success' | 'info' | 'warn' | 'danger' | 'secondary' } {
  if (run.stalled) {
    return { value: 'Stalled', severity: 'warn' };
  }
  switch (run.status) {
    case 'completed':
      return { value: 'Completed', severity: 'success' };
    case 'running':
      return { value: 'Running', severity: 'info' };
    case 'failed':
      return { value: 'Failed', severity: 'danger' };
    default:
      return { value: run.status.replace(/_/g, ' '), severity: 'secondary' };
  }
}

/**
 * The signed-in user's tool runs (G3-840): open, download, rerun and delete each.
 *
 * Runs live on AsyncTask; the API lists them as the user (`GET /tools/runs`), newest first,
 * and expires those past retention as it lists them.
 */
@Component({
  selector: 'app-analyses',
  imports: [
    ButtonModule,
    CardModule,
    DatePipe,
    MessageModule,
    RouterLink,
    RunActionsComponent,
    TableModule,
    TagModule,
    TooltipModule,
  ],
  templateUrl: './analyses.component.html',
})
export class AnalysesComponent implements OnInit {
  private readonly changes = inject(ChangeDetectorRef);
  private readonly router = inject(Router);
  readonly session = inject(SessionService);
  private readonly api: ApiBaseService = inject(ApiBaseServiceFactory).create(
    environment.urls.geneWeaverApi,
  );

  readonly rowsPerPage = RUNS_PER_PAGE;
  readonly toolLabel = toolLabel;
  readonly statusTag = statusTag;

  runs: ToolRunSummary[] = [];
  total = 0;
  first = 0;
  retentionDays?: number;
  expired = 0;
  expiring = 0;
  loading = false;
  errorMessage?: string;
  /** Runs with an action in flight, so their buttons cannot be pressed twice. */
  busy = new Set<number>();

  /**
   * The first page is fetched here, not by the table: a lazy table asks for it while the
   * page is being rendered, and changing the page's state then is an error in dev mode.
   */
  ngOnInit(): void {
    this.load(0);
  }

  /** The user asked the table for another page: fetch that one. */
  onPage(event: TableLazyLoadEvent): void {
    this.load(event.first ?? 0);
  }

  load(first: number): void {
    this.loading = true;
    this.errorMessage = undefined;
    this.api
      .get<ToolRunList>(
        '/tools/runs',
        new HttpParams({ fromObject: { limit: RUNS_PER_PAGE, offset: first } }),
      )
      .pipe(renderAfter(this.changes))
      .subscribe({
        next: (response) => {
          const list = response.object;
          this.runs = list?.runs ?? [];
          this.total = list?.total ?? 0;
          this.first = first;
          this.retentionDays = list?.retention_days;
          this.expired = list?.expired ?? 0;
          this.expiring = list?.expiring ?? 0;
          this.loading = false;
        },
        error: (error: HttpFailure) => {
          this.runs = [];
          this.loading = false;
          if (error?.status === 401) {
            this.session.refresh();
          }
          this.errorMessage = describeRunError(error, 'see your analyses');
        },
      });
  }

  /** Open a completed run on the Analyze page, which draws its result. */
  open(run: ToolRunSummary): void {
    this.router.navigate(['/analyze'], { queryParams: { run: run.run_id } });
  }

  /** Submit the run again; the Analyze page then shows the new run as it finishes. */
  rerun(run: ToolRunSummary): void {
    this.busy.add(run.run_id);
    this.errorMessage = undefined;
    this.api
      .post<{ run_id?: number | null }>(`/tools/runs/${run.run_id}/rerun`, {})
      .pipe(renderAfter(this.changes))
      .subscribe({
        next: (response) => {
          this.busy.delete(run.run_id);
          const newRun = response.object?.run_id;
          if (typeof newRun === 'number') {
            this.router.navigate(['/analyze'], { queryParams: { run: newRun } });
          } else {
            this.load(0);
          }
        },
        error: (error: HttpFailure) => {
          this.busy.delete(run.run_id);
          this.errorMessage = describeRunError(error, 'rerun that analysis');
        },
      });
  }

  /** Delete a run (stopping it first if it is still running), once confirmed. */
  remove(run: ToolRunSummary): void {
    const what = `${toolLabel(run.tool)} run ${run.run_id}`;
    if (!window.confirm(`Delete ${what}? Its result is deleted too, and cannot be recovered.`)) {
      return;
    }
    this.busy.add(run.run_id);
    this.errorMessage = undefined;
    this.api
      .delete<unknown>(`/tools/runs/${run.run_id}`)
      .pipe(renderAfter(this.changes))
      .subscribe({
        next: () => {
          this.busy.delete(run.run_id);
          // The last run on a page that is not the first: go back a page rather than show none.
          const first = this.runs.length === 1 && this.first > 0 ? this.first - RUNS_PER_PAGE : this.first;
          this.load(first);
        },
        error: (error: HttpFailure) => {
          this.busy.delete(run.run_id);
          this.errorMessage = describeRunError(error, 'delete that analysis');
        },
      });
  }
}
