/**
 * A user's tool runs on AsyncTask, as the API's run management serves them (G3-801), and
 * what the pages need to show and act on them (G3-840).
 */
import { environment } from '../../environments/environment';

/**
 * Display names for the registered tool keys. Unknown keys fall back to the key.
 * phenome_map, jaccard_clustering and triclique carry legacy's names (HiSim Graph, GeneSet
 * Clustering, TricliqueViewer), not the v3 registry keys, so people who know the legacy
 * tools can find them.
 */
export const TOOL_LABELS: Record<string, string> = {
  upset: 'UpSet',
  hypergeometric: 'HyperGeometric',
  dbscan: 'DBSCAN',
  geneset_graph: 'GeneSet Graph',
  triclique: 'TricliqueViewer',
  mset: 'MSET',
  phenome_map: 'HiSim Graph',
  boolean_algebra: 'BooleanAlgebra',
  combine: 'Combine',
  jaccard_clustering: 'GeneSet Clustering',
  jaccard_similarity: 'JaccardSimilarity',
  abba: 'ABBA gene search',
  similar_genesets: 'Similar GeneSets',
};

export function toolLabel(tool: string | null | undefined): string {
  return tool ? (TOOL_LABELS[tool] ?? tool) : 'Unknown tool';
}

/** One run in `GET /tools/runs`. */
export interface ToolRunSummary {
  run_id: number;
  /** None for a run from before runs recorded their request. */
  tool: string | null;
  name?: string | null;
  geneset_ids: number[] | null;
  status: string;
  /** Still running past the API's limit: it will not finish on its own. */
  stalled: boolean;
  /** What is known of a run that did not complete; AsyncTask records no reason (G3-839). */
  problem: string | null;
  created: string | null;
  can_rerun: boolean;
}

/** `GET /tools/runs`. */
export interface ToolRunList {
  runs: ToolRunSummary[];
  total: number;
  /** Runs past retention deleted by this listing. */
  expired: number;
  /** Runs past retention left for later listings (expiry is bounded per listing). */
  expiring: number;
  retention_days: number;
}

/** `GET /tools/runs/{run_id}`. `result` is the tool's own output once completed. */
export interface ToolRunDetail extends Omit<ToolRunSummary, 'name'> {
  workflow_id?: string | null;
  /** Gene sets in an ABBA or Similar gene sets result the caller can no longer read. */
  withheld_genesets?: number;
  result?: Record<string, unknown> | null;
}

/** One file a run's result downloads as. */
export interface RunDownload {
  label: string;
  format: string;
  table?: string;
}

/**
 * Each tool's tables, as `TABLES` in the API's `tool_downloads.py` names them; the first is
 * the default. Mirrored by hand, like the tool options: if a tool gains a table there, add it
 * here. A table this list lacks is still in the JSON download.
 */
const TABLES: Record<string, string[]> = {
  upset: ['intersections'],
  jaccard_similarity: ['pairs'],
  hypergeometric: ['pairs'],
  combine: ['matrix'],
  boolean_algebra: ['genes'],
  dbscan: ['clusters'],
  geneset_graph: ['genes', 'genesets'],
  triclique: ['shared_genes'],
  mset: ['summary'],
  phenome_map: ['nodes'],
  abba: ['genesets', 'genes'],
  similar_genesets: ['genesets'],
};

const TABLE_LABELS: Record<string, string> = {
  shared_genes: 'shared genes',
  genesets: 'gene sets',
};

/** What a run's result can be downloaded as: the API's `formats_for`, table by table. */
export function runDownloads(tool: string | null | undefined): RunDownload[] {
  const downloads: RunDownload[] = [];
  const tables = (tool && TABLES[tool]) || [];
  for (const table of tables) {
    const name = tables.length > 1 ? ` (${TABLE_LABELS[table] ?? table})` : '';
    downloads.push({ label: `CSV${name}`, format: 'csv', table });
    downloads.push({ label: `TSV${name}`, format: 'tsv', table });
  }
  if (tool === 'combine') {
    downloads.push({ label: 'ODEMAT (legacy matrix)', format: 'odemat' });
  }
  if (tool === 'jaccard_clustering') {
    downloads.push({ label: 'Newick tree', format: 'newick' });
  }
  downloads.push({ label: 'JSON (full result)', format: 'json' });
  return downloads;
}

/**
 * Where a download is served. A plain link, not a request from the page: the session cookie
 * goes with it (same site), and the browser saves the file under the API's own name.
 */
export function downloadUrl(runId: number, download: RunDownload): string {
  const params = new URLSearchParams({ format: download.format });
  if (download.table) {
    params.set('table', download.table);
  }
  return `${environment.urls.geneWeaverApi}/tools/runs/${runId}/download?${params}`;
}

/** The shape a failed request has. */
export interface HttpFailure {
  status?: number;
  error?: { detail?: string };
}

/** What to tell the user when a run action fails, by the API's status codes for runs. */
export function describeRunError(error: HttpFailure | undefined, action: string): string {
  const detail = error?.error?.detail;
  switch (error?.status) {
    case 401:
      return detail ?? `Sign in to ${action}.`;
    case 403:
      return (
        (detail ?? 'You can no longer read one or more of its gene sets.') +
        ' The run cannot be shown or rerun while they are not readable to you.'
      );
    case 404:
      return detail ?? 'That run is not one of yours, or it has been deleted.';
    case 409:
      return detail ?? 'That run cannot be used from here; run the analysis again.';
    case 422:
      return detail ?? 'That request was refused.';
    case 0:
      return `Could not reach the API at ${environment.urls.geneWeaverApi}.`;
    default:
      return detail ?? `Could not ${action} (HTTP ${error?.status ?? 'unknown'}).`;
  }
}

/**
 * Each gene set's size from UpSet's exclusive intersections: every gene is in exactly one
 * exclusive combination, so a gene set's size is the sum over the combinations it is in. A
 * stored run keeps only the intersections, not the counts the page showed when it ran.
 */
export function geneCountsFromIntersections(
  genesetIds: number[],
  intersections: { geneset_ids: string[]; size: number }[],
): Record<string, number> {
  const counts: Record<string, number> = Object.fromEntries(genesetIds.map((id) => [String(id), 0]));
  for (const intersection of intersections) {
    for (const id of intersection.geneset_ids) {
      counts[id] = (counts[id] ?? 0) + intersection.size;
    }
  }
  return counts;
}
