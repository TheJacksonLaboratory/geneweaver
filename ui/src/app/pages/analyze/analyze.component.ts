import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiBaseService, ApiBaseServiceFactory } from 'jax-apiutils';

/* PrimeNG Imports */
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { CheckboxModule } from 'primeng/checkbox';
import { ChipsModule } from 'primeng/chips';
import { DropdownModule } from 'primeng/dropdown';
import { MessageModule } from 'primeng/message';
import { ProgressBarModule } from 'primeng/progressbar';
import { TableModule } from 'primeng/table';

/* Local Imports */
import { environment } from '../../../environments/environment';

interface UpSetIntersection {
  geneset_ids: string[];
  size: number;
}

interface UpSetResult {
  tool: string;
  geneset_ids: number[];
  gene_counts: Record<string, number>;
  intersections: UpSetIntersection[];
}

interface ToolOption {
  label: string;
  value: string;
  /** Why a tool is not selectable yet, shown to the user. */
  disabledReason?: string;
}

/**
 * Run a GeneWeaver v3 analysis tool over gene sets and show the result.
 *
 * This is the first page that exercises the ported tools end to end: the API resolves
 * the gene sets from the database, runs the tool, and returns data. It intentionally
 * covers one tool -- UpSet -- because that is the one with no native binary and no
 * dependency on `gene_rank` or `jaccard_distribution_results`, which are empty across
 * local, dev and sqa.
 *
 * Runs are synchronous today. When tool execution moves to AsyncTask the API will return
 * a run id instead of a result, and this page grows status polling; the tool picker and
 * result table stay.
 */
@Component({
  selector: 'app-analyze',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ButtonModule,
    CardModule,
    CheckboxModule,
    ChipsModule,
    DropdownModule,
    MessageModule,
    ProgressBarModule,
    TableModule,
  ],
  templateUrl: './analyze.component.html',
})
export class AnalyzeComponent {
  private gwApi: ApiBaseService;

  /** Gene set ids as typed by the user; validated before the call. */
  genesetIdInput: string[] = [];
  includeZeros = false;
  selectedTool = 'upset';

  readonly tools: ToolOption[] = [
    { label: 'UpSet', value: 'upset' },
    {
      label: 'HyperGeometric',
      value: 'hypergeometric',
      disabledReason: 'Needs its contingency-table resolver (G3-798).',
    },
    {
      label: 'DBSCAN',
      value: 'dbscan',
      disabledReason: 'Needs its resolver (G3-798).',
    },
    {
      label: 'MSET',
      value: 'mset',
      disabledReason: 'Needs the DB-resolved gene universe (G3-784 / G3-798).',
    },
    {
      label: 'PhenomeMap',
      value: 'phenomemap',
      disabledReason: 'Blocked: the biclique binary SIGTRAPs (G3-804).',
    },
  ];

  running = false;
  result?: UpSetResult;
  errorMessage?: string;

  constructor(private apiBaseServiceFactory: ApiBaseServiceFactory) {
    this.gwApi = this.apiBaseServiceFactory.create(environment.urls.geneWeaverApi);
  }

  get toolOptions(): ToolOption[] {
    return this.tools.map((tool) => ({
      ...tool,
      label: tool.disabledReason ? `${tool.label} — not yet available` : tool.label,
    }));
  }

  get selectedToolReason(): string | undefined {
    return this.tools.find((tool) => tool.value === this.selectedTool)?.disabledReason;
  }

  /** Gene set ids that parsed as positive integers. */
  get genesetIds(): number[] {
    return this.genesetIdInput
      .map((value) => Number(String(value).trim()))
      .filter((value) => Number.isInteger(value) && value > 0);
  }

  get invalidEntries(): string[] {
    return this.genesetIdInput.filter((value) => {
      const parsed = Number(String(value).trim());
      return !Number.isInteger(parsed) || parsed <= 0;
    });
  }

  get canRun(): boolean {
    return (
      !this.running &&
      !this.selectedToolReason &&
      this.invalidEntries.length === 0 &&
      this.genesetIds.length >= 2
    );
  }

  /** Gene sets that resolved to no genes -- usually the reason an intersection is empty. */
  get emptyGenesets(): string[] {
    if (!this.result) {
      return [];
    }
    return Object.entries(this.result.gene_counts)
      .filter(([, count]) => count === 0)
      .map(([genesetId]) => genesetId);
  }

  run(): void {
    if (!this.canRun) {
      return;
    }
    this.running = true;
    this.result = undefined;
    this.errorMessage = undefined;

    this.gwApi
      .post<UpSetResult>(`/tools/${this.selectedTool}`, {
        geneset_ids: this.genesetIds,
        include_zeros: this.includeZeros,
      })
      .subscribe({
        next: (response) => {
          this.result = response.object;
          this.running = false;
        },
        error: (error) => {
          this.errorMessage = this.describeError(error);
          this.running = false;
        },
      });
  }

  clear(): void {
    this.result = undefined;
    this.errorMessage = undefined;
  }

  /** Turn an HTTP failure into something a user can act on. */
  private describeError(error: { status?: number; error?: { detail?: string } }): string {
    const detail = error?.error?.detail;
    if (error?.status === 403) {
      return (
        detail ??
        'Not authorised to read one or more of those gene sets. Signed-out runs can only ' +
          'use publicly readable gene sets.'
      );
    }
    if (error?.status === 422) {
      return detail ?? 'Those parameters were rejected. Check the gene set ids.';
    }
    if (error?.status === 0) {
      return `Could not reach the API at ${environment.urls.geneWeaverApi}. Is it running?`;
    }
    return detail ?? `The run failed (HTTP ${error?.status ?? 'unknown'}).`;
  }

  label(intersection: UpSetIntersection): string {
    return intersection.geneset_ids.join(' ∩ ');
  }
}
