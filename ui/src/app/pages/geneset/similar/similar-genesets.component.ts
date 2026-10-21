import { NgFor, NgIf, DecimalPipe } from '@angular/common';
import { Component, Input, OnChanges, OnDestroy, SimpleChanges } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiBaseService, ApiBaseServiceFactory } from 'jax-apiutils';
import { ButtonModule } from 'primeng/button';
import { InputNumberModule } from 'primeng/inputnumber';
import { ProgressBarModule } from 'primeng/progressbar';
import { Subscription, map, switchMap, takeWhile, timer } from 'rxjs';

import { environment } from '../../../../environments/environment';
import { SessionService } from '../../../services/session.service';
import {
  defaultRunThresholds,
  describeThresholds,
  RunThresholds,
  THRESHOLD_MODES,
  thresholdParams,
  thresholdProblem,
} from '../../analyze/run-thresholds';
import {
  GROUP_BY_CHOICES,
  GroupBy,
  groupSimilar,
  radarAxis,
  RadarModel,
  radarModel,
  radarPoints,
  similarCsv,
  SimilarGenesetsOutput,
  SimilarGroup,
  speciesLabel,
  tierLabel,
} from './similar-models';

/** How often a running search is polled. Searches take about two minutes. */
export const SIMILAR_POLL_INTERVAL_MS = 3000;

/** Rows shown before "Show all". Legacy's page listed every one of its 500 at once. */
const PAGE = 50;

/** Tableau 10, one colour per tier, as the analyze charts use. */
const TIER_COLOURS = ['#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F'];

const RADAR_RADIUS = 120;

interface RunBody {
  run_id?: number | null;
  status?: string;
  result?: SimilarGenesetsOutput;
}

interface HttpFailure {
  status?: number;
  error?: { detail?: string };
}

/**
 * Similar gene sets, legacy's "Find Similar GeneSets", as a section of the gene set page.
 *
 * Started by the user rather than on page load: it reads every gene of every gene set
 * sharing a gene with this one, about two minutes, so it runs on AsyncTask and is polled.
 * Nothing is cached, so each run computes afresh with the chosen threshold.
 */
@Component({
  selector: 'app-similar-genesets',
  standalone: true,
  imports: [NgIf, NgFor, DecimalPipe, FormsModule, RouterLink, ButtonModule, InputNumberModule, ProgressBarModule],
  template: `
    <p class="text-sm text-color-secondary mt-0 text-left">
      The gene sets sharing the most genes with this one, by Jaccard: shared genes ÷ all genes of
      the two. Homologs count as one gene, so gene sets of other species are compared too.
    </p>

    <p *ngIf="!signedIn" class="text-left">Sign in to find similar gene sets.</p>

    <ng-container *ngIf="signedIn">
      <fieldset class="border-none p-0 mx-0 mb-3 text-left">
        <legend class="mb-2">Gene set thresholds</legend>
        <div class="flex flex-wrap gap-3" role="radiogroup" aria-label="Gene set thresholds">
          <div *ngFor="let mode of thresholdModes" class="flex align-items-center">
            <input
              type="radio"
              name="similarThreshold"
              [id]="'similar-threshold-' + mode.value"
              [value]="mode.value"
              [(ngModel)]="thresholds.mode"
              [disabled]="running"
            />
            <label [for]="'similar-threshold-' + mode.value" class="ml-2">{{ mode.label }}</label>
          </div>
        </div>
        <div *ngIf="thresholds.mode === 'custom'" class="formgrid grid mt-2">
          <div class="field col-6 md:col-3">
            <label for="similar-cutoff-p" class="block mb-1 text-sm">p-value at most</label>
            <p-inputNumber inputId="similar-cutoff-p" [(ngModel)]="thresholds.pValue" mode="decimal"
              [maxFractionDigits]="8" [min]="0" [max]="1" styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
          </div>
          <div class="field col-6 md:col-3">
            <label for="similar-cutoff-q" class="block mb-1 text-sm">q-value at most</label>
            <p-inputNumber inputId="similar-cutoff-q" [(ngModel)]="thresholds.qValue" mode="decimal"
              [maxFractionDigits]="8" [min]="0" [max]="1" styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
          </div>
          <div class="field col-6 md:col-3">
            <label for="similar-corr-low" class="block mb-1 text-sm">Correlation from / to</label>
            <div class="flex gap-1">
              <p-inputNumber inputId="similar-corr-low" [(ngModel)]="thresholds.correlationLow" mode="decimal"
                [maxFractionDigits]="6" ariaLabel="Correlation from" styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
              <p-inputNumber inputId="similar-corr-high" [(ngModel)]="thresholds.correlationHigh" mode="decimal"
                [maxFractionDigits]="6" ariaLabel="Correlation to" styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
            </div>
          </div>
          <div class="field col-6 md:col-3">
            <label for="similar-effect-low" class="block mb-1 text-sm">Effect from / to</label>
            <div class="flex gap-1">
              <p-inputNumber inputId="similar-effect-low" [(ngModel)]="thresholds.effectLow" mode="decimal"
                [maxFractionDigits]="6" ariaLabel="Effect from" styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
              <p-inputNumber inputId="similar-effect-high" [(ngModel)]="thresholds.effectHigh" mode="decimal"
                [maxFractionDigits]="6" ariaLabel="Effect to" styleClass="w-full" inputStyleClass="w-full"></p-inputNumber>
            </div>
          </div>
        </div>
        <small *ngIf="problem" class="block text-orange-600 similar-problem">{{ problem }}</small>
      </fieldset>

      <div class="flex align-items-center gap-3 mb-3">
        <p-button
          [label]="result ? 'Find again' : 'Find similar gene sets'"
          icon="pi pi-search"
          (onClick)="run()"
          [disabled]="running || !!problem"
        ></p-button>
        <span *ngIf="running" class="text-sm text-color-secondary">
          Comparing with every gene set that shares a gene: this takes about two minutes.
        </span>
      </div>
      <p-progressBar *ngIf="running" mode="indeterminate" styleClass="mb-3" [style]="{ height: '4px' }"></p-progressBar>
      <p *ngIf="errorMessage" class="text-red-600 text-left similar-error" role="alert">{{ errorMessage }}</p>
    </ng-container>

    <ng-container *ngIf="result">
      <p class="text-sm text-left">
        {{ result.genesets.length }} of the {{ result.compared | number }} gene sets sharing a gene with
        GS{{ result.geneset_id }} ({{ result.genes }} genes). {{ describe(result) }}
      </p>

      <ng-container *ngIf="result.genesets.length; else none">
        <div class="grid">
          <figure class="col-12 md:col-6 m-0">
            <figcaption class="text-sm font-bold text-left mb-2">Average Jaccard by tier and species</figcaption>
            <svg
              *ngIf="radar.axes.length >= 3; else fewSpecies"
              viewBox="-200 -160 400 320"
              class="w-full"
              role="img"
              [attr.aria-label]="radarLabel"
              style="max-height: 320px; font: 10px sans-serif"
            >
              <g fill="none" stroke="#CBD5E1">
                <polygon *ngFor="let ring of rings" [attr.points]="ring"></polygon>
                <line *ngFor="let axis of radarAxes" x1="0" y1="0" [attr.x2]="axis.x" [attr.y2]="axis.y"></line>
              </g>
              <text
                *ngFor="let axis of radarAxes"
                [attr.x]="axis.lx"
                [attr.y]="axis.ly"
                [attr.text-anchor]="axis.anchor"
                dy="0.35em"
              >{{ axis.label }}</text>
              <polygon
                *ngFor="let series of radarSeries"
                [attr.points]="series.points"
                [attr.fill]="series.colour"
                fill-opacity="0.15"
                [attr.stroke]="series.colour"
                stroke-width="1.5"
              ><title>{{ series.label }}</title></polygon>
            </svg>
            <ng-template #fewSpecies>
              <table class="text-sm w-full">
                <thead><tr><th scope="col" class="text-left">Tier</th><th scope="col" *ngFor="let axis of radar.axes" class="text-left">{{ axis }}</th></tr></thead>
                <tbody>
                  <tr *ngFor="let series of radar.series">
                    <td>{{ series.label }}</td>
                    <td *ngFor="let value of series.values">{{ value | number: '1.4-4' }}</td>
                  </tr>
                </tbody>
              </table>
            </ng-template>
            <ul class="list-none p-0 m-0 mt-2 flex flex-wrap gap-3 text-sm">
              <li *ngFor="let series of radarSeries">
                <span class="swatch" [style.background]="series.colour"></span>{{ series.label }} ({{ series.count }})
              </li>
            </ul>
          </figure>
          <figure class="col-12 md:col-6 m-0">
            <figcaption class="text-sm font-bold text-left mb-2">Jaccard by rank</figcaption>
            <svg
              [attr.viewBox]="'0 0 ' + barWidth + ' 200'"
              class="w-full"
              preserveAspectRatio="none"
              role="img"
              [attr.aria-label]="'Jaccard of the ' + result.genesets.length + ' gene sets, most similar first'"
              style="max-height: 220px"
            >
              <rect
                *ngFor="let bar of bars"
                [attr.x]="bar.x"
                [attr.y]="200 - bar.height"
                [attr.width]="bar.width"
                [attr.height]="bar.height"
                [attr.fill]="bar.colour"
              ><title>{{ bar.title }}</title></rect>
            </svg>
            <p class="text-xs text-color-secondary m-0 text-left">Coloured by tier; the tallest is {{ result.genesets[0].jaccard | number: '1.4-4' }}.</p>
          </figure>
        </div>

        <div class="flex flex-wrap align-items-center gap-3 my-3">
          <label for="similar-group" class="text-sm">Group by</label>
          <!-- (input), not ngModel: the test DOM fires a spurious change as options are
               inserted (as on /next/analyze). Browsers fire input for every choice. -->
          <select id="similar-group" class="p-inputtext" (input)="setGroupIndex($any($event.target).selectedIndex)">
            <option *ngFor="let choice of groupChoices" [selected]="choice.value === groupBy">{{ choice.label }}</option>
          </select>
          <button type="button" class="p-button p-button-sm p-button-text" (click)="downloadCsv()">
            Download CSV
          </button>
        </div>

        <table class="similar-table text-sm w-full">
          <thead>
            <tr>
              <th scope="col">Gene set</th>
              <th scope="col">Name</th>
              <th scope="col">Species</th>
              <th scope="col">Tier</th>
              <th scope="col" class="text-right">Genes</th>
              <th scope="col" class="text-right">Shared</th>
              <th scope="col" class="text-right">Jaccard</th>
            </tr>
          </thead>
          <tbody *ngFor="let group of shownGroups">
            <tr *ngIf="group.label" class="group-row">
              <th colspan="7" scope="colgroup" class="text-left">{{ group.label }} ({{ group.genesets.length }})</th>
            </tr>
            <tr *ngFor="let gs of group.genesets">
              <td><a [routerLink]="['/geneset', gs.gs_id]">GS{{ gs.gs_id }}</a></td>
              <td class="text-left">{{ gs.abbreviation || gs.name }}</td>
              <td>{{ species(gs.species_id) }}</td>
              <td>{{ tier(gs.tier) }}</td>
              <td class="text-right">{{ gs.genes }}</td>
              <td class="text-right">{{ gs.shared }}</td>
              <td class="text-right">{{ gs.jaccard | number: '1.4-4' }}</td>
            </tr>
          </tbody>
        </table>
        <button
          *ngIf="!showAll && result.genesets.length > page"
          type="button"
          class="p-button p-button-sm p-button-text mt-2"
          (click)="showAll = true; regroup()"
        >
          Show all {{ result.genesets.length }}
        </button>
      </ng-container>
      <ng-template #none><p class="text-left">No other gene set you can read shares a gene with this one.</p></ng-template>
    </ng-container>
  `,
  styles: [
    '.swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; }',
    '.similar-table th, .similar-table td { padding: 0.35rem 0.5rem; border-bottom: 1px solid #E2E8F0; text-align: left; }',
    '.similar-table .text-right { text-align: right; }',
    '.group-row th { background: #F1F5F9; }',
  ],
})
export class SimilarGenesetsComponent implements OnChanges, OnDestroy {
  @Input({ required: true }) genesetId!: number;

  readonly thresholdModes = THRESHOLD_MODES;
  readonly groupChoices = GROUP_BY_CHOICES;
  readonly page = PAGE;
  thresholds: RunThresholds = defaultRunThresholds();
  running = false;
  errorMessage?: string;
  result?: SimilarGenesetsOutput;
  groupBy: GroupBy = 'none';
  showAll = false;
  shownGroups: SimilarGroup[] = [];
  radar: RadarModel = { axes: [], series: [], max: 0 };
  radarAxes: { x: number; y: number; lx: number; ly: number; anchor: string; label: string }[] = [];
  radarSeries: { label: string; colour: string; points: string; count: number }[] = [];
  rings: string[] = [];
  radarLabel = '';
  bars: { x: number; width: number; height: number; colour: string; title: string }[] = [];
  barWidth = 500;

  private gwApi: ApiBaseService;
  private poll?: Subscription;

  constructor(
    apiBaseServiceFactory: ApiBaseServiceFactory,
    private session: SessionService,
  ) {
    this.gwApi = apiBaseServiceFactory.create(environment.urls.geneWeaverApi);
  }

  get signedIn(): boolean {
    return this.session.authenticated;
  }

  get problem(): string | undefined {
    return thresholdProblem(this.thresholds);
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['genesetId'] && !changes['genesetId'].firstChange) {
      // Another gene set: its own search, not this one's result.
      this.stop();
      this.result = undefined;
      this.errorMessage = undefined;
      this.running = false;
    }
  }

  ngOnDestroy(): void {
    this.stop();
  }

  run(): void {
    if (this.running || this.problem) {
      return;
    }
    this.stop();
    this.running = true;
    this.errorMessage = undefined;
    this.gwApi
      .post<RunBody>('/tools/similar_genesets', {
        geneset_id: this.genesetId,
        ...thresholdParams(this.thresholds),
      })
      .subscribe({
        next: (response) => {
          const body = response.object as RunBody | undefined;
          if (body && typeof body.run_id === 'number' && body.status === 'running' && !body.result) {
            this.pollRun(body.run_id);
            return;
          }
          this.show(body?.result);
        },
        error: (error: HttpFailure) => this.fail(error),
      });
  }

  private pollRun(runId: number): void {
    this.poll = timer(SIMILAR_POLL_INTERVAL_MS, SIMILAR_POLL_INTERVAL_MS)
      .pipe(
        switchMap(() => this.gwApi.get<RunBody & { workflow_id?: string }>(`/tools/runs/${runId}`)),
        map((response) => response.object as RunBody & { workflow_id?: string }),
        takeWhile((run) => run.status === 'running', true),
      )
      .subscribe({
        next: (run) => {
          if (run.status === 'running') {
            return;
          }
          if (run.status !== 'completed' || !run.result) {
            this.running = false;
            this.errorMessage =
              `The search ended ${run.status}` + (run.workflow_id ? ` (workflow ${run.workflow_id}).` : '.');
            return;
          }
          this.show(run.result);
        },
        error: (error: HttpFailure) => this.fail(error),
      });
  }

  private show(result: SimilarGenesetsOutput | undefined): void {
    this.running = false;
    if (!result) {
      this.errorMessage = 'The search returned no result.';
      return;
    }
    this.result = result;
    this.showAll = false;
    this.regroup();
    this.drawRadar();
    this.drawBars();
  }

  private fail(error: HttpFailure): void {
    this.running = false;
    const detail = error?.error?.detail;
    if (error?.status === 401) {
      this.session.refresh();
      this.errorMessage = detail ?? 'Sign in to find similar gene sets.';
    } else if (error?.status === 403) {
      this.errorMessage = detail ?? 'You may not read this gene set.';
    } else if (error?.status === 503) {
      this.errorMessage = detail ?? 'A search is already running. Try again in a few minutes.';
    } else {
      this.errorMessage = detail ?? `The search failed (HTTP ${error?.status ?? 'unknown'}).`;
    }
  }

  private stop(): void {
    this.poll?.unsubscribe();
    this.poll = undefined;
  }

  setGroup(value: GroupBy): void {
    this.groupBy = value;
    this.regroup();
  }

  setGroupIndex(index: number): void {
    const choice = GROUP_BY_CHOICES[index];
    if (choice) {
      this.setGroup(choice.value);
    }
  }

  regroup(): void {
    if (!this.result) {
      return;
    }
    const limited = this.showAll
      ? this.result
      : { ...this.result, genesets: this.result.genesets.slice(0, PAGE) };
    this.shownGroups = groupSimilar(limited, this.groupBy);
  }

  species(id: number): string {
    return this.result ? speciesLabel(this.result, id) : String(id);
  }

  tier(id: number): string {
    return this.result ? tierLabel(this.result, id) : String(id);
  }

  describe(result: SimilarGenesetsOutput): string {
    return describeThresholds(result.thresholds);
  }

  private drawRadar(): void {
    if (!this.result) {
      return;
    }
    this.radar = radarModel(this.result);
    const n = this.radar.axes.length;
    this.radarAxes = this.radar.axes.map((label, i) => {
      const end = radarAxis(i, n, RADAR_RADIUS);
      const at = radarAxis(i, n, RADAR_RADIUS + 12);
      return {
        ...end,
        lx: at.x,
        ly: at.y,
        anchor: Math.abs(at.x) < 1 ? 'middle' : at.x > 0 ? 'start' : 'end',
        label,
      };
    });
    this.rings = [0.25, 0.5, 0.75, 1].map((f) => radarPoints(new Array(n).fill(f), 1, RADAR_RADIUS));
    this.radarSeries = this.radar.series.map((series) => ({
      label: series.label,
      count: series.count,
      colour: TIER_COLOURS[(series.tier - 1) % TIER_COLOURS.length],
      points: radarPoints(series.values, this.radar.max, RADAR_RADIUS),
    }));
    this.radarLabel =
      `Average Jaccard per species for ${this.radar.series.length} tiers; ` +
      `the outer ring is ${this.radar.max.toFixed(4)}.`;
  }

  private drawBars(): void {
    if (!this.result) {
      return;
    }
    const list = this.result.genesets;
    const width = this.barWidth / Math.max(1, list.length);
    const top = list[0]?.jaccard || 1;
    this.bars = list.map((gs, i) => ({
      x: i * width,
      width: Math.max(width - (width > 3 ? 1 : 0), 0.5),
      height: (gs.jaccard / top) * 195,
      colour: TIER_COLOURS[(gs.tier - 1) % TIER_COLOURS.length],
      title: `${i + 1}. GS${gs.gs_id}: ${gs.jaccard.toFixed(4)}`,
    }));
  }

  downloadCsv(): void {
    if (!this.result) {
      return;
    }
    const blob = new Blob([similarCsv(this.result)], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `GS${this.result.geneset_id}-similar-genesets.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }
}
