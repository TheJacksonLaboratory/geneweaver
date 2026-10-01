import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiBaseService, ApiBaseServiceFactory } from 'jax-apiutils';

/* PrimeNG Imports */
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { CheckboxModule } from 'primeng/checkbox';
import { ChipsModule } from 'primeng/chips';
import { DropdownModule } from 'primeng/dropdown';
import { InputTextModule } from 'primeng/inputtext';
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

/**
 * Request bounds, mirroring `UpSetRequest` in `api/schemas/tools.py`.
 *
 * Duplicated deliberately: the point is to say *why* a run is rejected before spending a
 * round trip on a 422 whose generic detail the user cannot act on. If the API bounds move,
 * these move with them -- `test_upset_request_bounds_match_the_ui` in the API suite fails
 * if they diverge.
 */
const MAX_GENESETS = 20;
const MIN_GENESETS = 2;
/** Combinations grow as 2^n - 1, so expanding the empty ones is capped lower. */
const MAX_GENESETS_WITH_ZEROS = 10;

interface ToolOption {
  label: string;
  value: string;
  /** Why a tool is not selectable yet, shown to the user. */
  disabledReason?: string;
  /** Qualifies how a successful result should be read, if anything does. */
  caveat?: string;
}

interface ToolRunResult {
  tool: string;
  geneset_ids: number[];
  gene_counts: Record<string, number>;
  caveat?: string | null;
  result: Record<string, unknown>;
}

/** Either response shape, so the two request branches unify. */
type AnyToolResult = UpSetResult | ToolRunResult;

/** The shape `describeError` reads off a failed request. */
interface HttpFailure {
  status?: number;
  error?: { detail?: string };
}

interface ToolAvailability {
  available: boolean;
  reason?: string | null;
  caveat?: string | null;
}

/** Display names for the registered tool keys. Unknown keys fall back to the key. */
const TOOL_LABELS: Record<string, string> = {
  upset: 'UpSet',
  hypergeometric: 'HyperGeometric',
  dbscan: 'DBSCAN',
  mset: 'MSET',
  phenome_map: 'PhenomeMap',
  boolean_algebra: 'BooleanAlgebra',
  combine: 'Combine',
  jaccard_clustering: 'JaccardClustering',
  jaccard_similarity: 'JaccardSimilarity',
};

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
    InputTextModule,
    MessageModule,
    ProgressBarModule,
    TableModule,
  ],
  templateUrl: './analyze.component.html',
})
export class AnalyzeComponent implements OnInit {
  private gwApi: ApiBaseService;

  /** Gene set ids as typed by the user; validated before the call. */
  genesetIdInput: string[] = [];
  includeZeros = false;
  selectedTool = 'upset';

  /**
   * Loaded from `GET /tools` rather than hardcoded.
   *
   * This list used to name five of the nine tools, so four -- BooleanAlgebra, Combine,
   * JaccardClustering, JaccardSimilarity -- were invisible, and the page understated the
   * port. The API knows what is registered and what can actually run, so it is the only
   * thing that cannot drift from reality.
   */
  tools: ToolOption[] = [];
  toolsLoading = true;
  toolsError?: string;

  running = false;
  result?: UpSetResult;
  genericResult?: ToolRunResult;
  errorMessage?: string;

  /** DBSCAN parameters; its schema requires both. Defaults match the smallest case the
   * validation harness exercises. */
  epsilon = 1;
  minPoints = 2;
  /** BooleanAlgebra's operation. */
  relation: 'union' | 'intersection' | 'except' = 'intersection';

  constructor(private apiBaseServiceFactory: ApiBaseServiceFactory) {
    this.gwApi = this.apiBaseServiceFactory.create(environment.urls.geneWeaverApi);
  }

  ngOnInit(): void {
    this.loadTools();
  }

  /** Fetch the registered tools and whether each can run. */
  private loadTools(): void {
    this.gwApi.get<{ tools: Record<string, ToolAvailability> }>('/tools').subscribe({
      next: (response) => {
        const tools = response.object?.tools ?? {};
        this.tools = Object.entries(tools)
          .map(([value, state]) => ({
            value,
            label: TOOL_LABELS[value] ?? value,
            disabledReason: state.available ? undefined : (state.reason ?? undefined),
            caveat: state.caveat ?? undefined,
          }))
          // Runnable tools first, then alphabetical, so the usable ones are not buried
          // among the blocked ones.
          .sort(
            (a, b) =>
              Number(!!a.disabledReason) - Number(!!b.disabledReason) ||
              a.label.localeCompare(b.label),
          );
        // Prefer UpSet: it is the one tool with a real visualisation rather than a raw
        // result dump, so it is the most useful default. Fall back to whatever else runs.
        const preferred =
          this.tools.find((tool) => tool.value === 'upset' && !tool.disabledReason) ??
          this.tools.find((tool) => !tool.disabledReason);
        if (preferred) {
          this.selectedTool = preferred.value;
        }
        this.toolsLoading = false;
      },
      error: (error: HttpFailure) => {
        this.toolsError = this.describeError(error);
        this.toolsLoading = false;
      },
    });
  }

  get selectedToolCaveat(): string | undefined {
    return this.tools.find((tool) => tool.value === this.selectedTool)?.caveat;
  }

  /** UpSet has a bespoke endpoint and plot; everything else uses the generic one. */
  get isUpSet(): boolean {
    return this.selectedTool === 'upset';
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

  /**
   * Why the current selection cannot be run, or `undefined` if it can.
   *
   * Reported locally rather than as a server 422: the API's detail message is correct but
   * arrives after the request, and the Run button should not offer a call that is known to
   * fail.
   */
  get limitViolation(): string | undefined {
    const count = this.genesetIds.length;
    if (count < MIN_GENESETS) {
      return undefined; // Not an error yet -- the user is still typing.
    }
    if (count > MAX_GENESETS) {
      return `Select at most ${MAX_GENESETS} gene sets; ${count} entered.`;
    }
    if (this.isUpSet && this.includeZeros && count > MAX_GENESETS_WITH_ZEROS) {
      return (
        `Including empty combinations is limited to ${MAX_GENESETS_WITH_ZEROS} gene sets ` +
        `(${count} entered), because the number of combinations grows as 2^n - 1. ` +
        `Clear the checkbox, or use fewer gene sets.`
      );
    }
    return undefined;
  }

  get canRun(): boolean {
    return (
      !this.running &&
      !this.toolsLoading &&
      this.tools.length > 0 &&
      !this.selectedToolReason &&
      this.invalidEntries.length === 0 &&
      this.genesetIds.length >= MIN_GENESETS &&
      !this.limitViolation
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
    this.genericResult = undefined;
    this.errorMessage = undefined;

    // UpSet keeps its own endpoint because the plot reads a typed, reshaped response.
    // Every other tool returns its own output verbatim, which this page renders as JSON
    // until each gets a proper visualisation (the ported tools dropped legacy's SVG, so
    // every chart is net-new front-end work).
    // Both branches take the same type parameter so the two observables unify -- a
    // union of differently-typed observables has no callable `subscribe`.
    const request$ = this.isUpSet
      ? this.gwApi.post<AnyToolResult>('/tools/upset', {
          geneset_ids: this.genesetIds,
          include_zeros: this.includeZeros,
        })
      : this.gwApi.post<AnyToolResult>(`/tools/${this.selectedTool}`, {
          geneset_ids: this.genesetIds,
          parameters: this.toolParameters(),
        });

    request$.subscribe({
      next: (response) => {
        if (this.isUpSet) {
          this.result = response.object as UpSetResult;
        } else {
          this.genericResult = response.object as ToolRunResult;
        }
        this.running = false;
      },
      error: (error: HttpFailure) => {
        this.errorMessage = this.describeError(error);
        this.running = false;
      },
    });
  }

  /**
   * Options for the selected tool.
   *
   * Only the few that have no workable default are sent. DBSCAN's epsilon/min_points are
   * required by its schema, and BooleanAlgebra needs a relation; the rest of the tools
   * default sensibly server-side. When runs move to AsyncTask these come from
   * `odestatic.tool_param` and the form is generated rather than written (roadmap A5).
   */
  private toolParameters(): Record<string, unknown> {
    switch (this.selectedTool) {
      case 'dbscan':
        return { epsilon: this.epsilon, min_points: this.minPoints };
      case 'boolean_algebra':
        return { relation: this.relation };
      default:
        return {};
    }
  }

  clear(): void {
    this.result = undefined;
    this.genericResult = undefined;
    this.errorMessage = undefined;
  }

  /** Turn an HTTP failure into something a user can act on. */
  private describeError(error: HttpFailure): string {
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
