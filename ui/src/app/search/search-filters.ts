/**
 * Gene set search filters, shared by the /next search page and the analyze page's gene set
 * picker: multi-criteria filters and sorting (G3-777), and a gene's score cutoffs per score
 * type (G3-764). Pure, so the mapping to the API and to the URL is tested without a DOM.
 *
 * The API is `GET /genesets/search` (`GenesetSearch` in `api/schemas/search.py`).
 */
import { HttpParams } from '@angular/common/http';

export type SortKey = 'id' | 'name' | 'size' | 'species' | 'tier' | 'score_type' | 'created' | 'updated';
export type SortOrder = 'asc' | 'desc';
/** With a gene and cutoffs: only the gene sets that pass, or all holding the gene, passing first. */
export type ThresholdMode = 'only' | 'first';

export interface SearchFilters {
  /** `sp_id`s. */
  species: number[];
  /** `cur_id`s, 1 (Tier I) to 5 (Tier V). */
  tiers: number[];
  /** `gs_threshold_type`s. */
  scoreTypes: number[];
  sizeMin: number | null;
  sizeMax: number | null;
  /** A gene, by any identifier; only gene sets holding it. */
  gene: string;
  pValue: number | null;
  qValue: number | null;
  correlationLow: number | null;
  correlationHigh: number | null;
  effectLow: number | null;
  effectHigh: number | null;
  thresholdMode: ThresholdMode;
}

export interface Sort {
  by: SortKey | null;
  order: SortOrder;
}

export interface Option {
  id: number;
  label: string;
  /** The value `GET /genesets/search` takes, from `geneweaver.core.enum`. */
  api: string;
}

/** `SpeciesInt` / `Species`. */
export const SPECIES_OPTIONS: Option[] = [
  { id: 1, label: 'Mus musculus', api: 'Mus Musculus' },
  { id: 2, label: 'Homo sapiens', api: 'Homo Sapiens' },
  { id: 3, label: 'Rattus norvegicus', api: 'Rattus Norvegicus' },
  { id: 4, label: 'Danio rerio', api: 'Danio Rerio' },
  { id: 5, label: 'Drosophila melanogaster', api: 'Drosophila Melanogaster' },
  { id: 6, label: 'Macaca mulatta', api: 'Macaca Mulatta' },
  { id: 8, label: 'Caenorhabditis elegans', api: 'Caenorhabditis Elegans' },
  { id: 9, label: 'Saccharomyces cerevisiae', api: 'Saccharomyces Cerevisiae' },
  { id: 10, label: 'Gallus gallus', api: 'Gallus Gallus' },
  { id: 11, label: 'Canis familiaris', api: 'Canis Familiaris' },
  { id: 12, label: 'Xenopus tropicalis', api: 'Xenopus Tropicalis' },
  { id: 13, label: 'Xenopus laevis', api: 'Xenopus Laevis' },
];

/** `GenesetTierInt` / `GenesetTier`. */
export const TIER_OPTIONS: Option[] = [1, 2, 3, 4, 5].map((id) => ({
  id,
  label: `Tier ${['I', 'II', 'III', 'IV', 'V'][id - 1]}`,
  api: `Tier ${['I', 'II', 'III', 'IV', 'V'][id - 1]}`,
}));

/** `ScoreTypeInt` / `ScoreType`. */
export const SCORE_TYPE_OPTIONS: Option[] = [
  { id: 1, label: 'p-value', api: 'p-value' },
  { id: 2, label: 'q-value', api: 'q-value' },
  { id: 3, label: 'Binary', api: 'binary' },
  { id: 4, label: 'Correlation', api: 'correlation' },
  { id: 5, label: 'Effect', api: 'effect' },
];

export const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'id', label: 'ID' },
  { value: 'name', label: 'Name' },
  { value: 'size', label: 'Size' },
  { value: 'species', label: 'Species' },
  { value: 'tier', label: 'Tier' },
  { value: 'score_type', label: 'Score type' },
  { value: 'created', label: 'Created' },
  { value: 'updated', label: 'Updated' },
];

export function emptyFilters(): SearchFilters {
  return {
    species: [],
    tiers: [],
    scoreTypes: [],
    sizeMin: null,
    sizeMax: null,
    gene: '',
    pValue: null,
    qValue: null,
    correlationLow: null,
    correlationHigh: null,
    effectLow: null,
    effectHigh: null,
    thresholdMode: 'only',
  };
}

const CUTOFFS = ['pValue', 'qValue', 'correlationLow', 'correlationHigh', 'effectLow', 'effectHigh'] as const;

/** Whether any cutoff is set; they only mean something with a gene. */
export function hasCutoffs(filters: SearchFilters): boolean {
  return CUTOFFS.some((key) => filters[key] !== null && filters[key] !== undefined);
}

/** How many filters are set, for the "Filters (n)" toggle. */
export function activeFilterCount(filters: SearchFilters): number {
  return (
    Number(filters.species.length > 0) +
    Number(filters.tiers.length > 0) +
    Number(filters.scoreTypes.length > 0) +
    Number(filters.sizeMin !== null || filters.sizeMax !== null) +
    Number(!!filters.gene.trim()) +
    Number(!!filters.gene.trim() && hasCutoffs(filters))
  );
}

/** A search needs text or a gene. */
export function canSearch(text: string, filters: SearchFilters): boolean {
  return !!text.trim() || !!filters.gene.trim();
}

/** Why these filters cannot be sent, or `undefined`. */
export function filterProblem(filters: SearchFilters): string | undefined {
  if (filters.sizeMin !== null && filters.sizeMax !== null && filters.sizeMin > filters.sizeMax) {
    return 'The smallest size is above the largest.';
  }
  for (const [name, low, high] of [
    ['correlation', filters.correlationLow, filters.correlationHigh],
    ['effect', filters.effectLow, filters.effectHigh],
  ] as const) {
    if (low !== null && high !== null && low > high) {
      return `The ${name} range's low end is above its high end.`;
    }
  }
  if (!filters.gene.trim() && hasCutoffs(filters)) {
    return 'Score cutoffs apply to a gene: enter one, or clear the cutoffs.';
  }
  return undefined;
}

const nameFor = (options: Option[], id: number) => options.find((option) => option.id === id)?.api;

/**
 * The `GET /genesets/search` parameters. Empty filters are left out; cutoffs are left out
 * without a gene, since the API refuses them alone.
 */
export function searchParams(
  text: string,
  filters: SearchFilters,
  page: { offset: number; limit: number },
  sort: Sort = { by: null, order: 'asc' },
): HttpParams {
  let params = new HttpParams().set('limit', page.limit).set('offset', page.offset);
  if (text.trim()) {
    params = params.set('search_text', text.trim());
  }
  for (const [key, options, ids] of [
    ['species', SPECIES_OPTIONS, filters.species],
    ['curation_tier', TIER_OPTIONS, filters.tiers],
    ['score_type', SCORE_TYPE_OPTIONS, filters.scoreTypes],
  ] as const) {
    for (const id of ids) {
      const name = nameFor(options, id);
      if (name) {
        params = params.append(key, name);
      }
    }
  }
  if (filters.sizeMin !== null) {
    params = params.set('gte_count', filters.sizeMin);
  }
  if (filters.sizeMax !== null) {
    params = params.set('lte_count', filters.sizeMax);
  }
  const gene = filters.gene.trim();
  if (gene) {
    params = params.set('gene', gene);
    for (const [key, value] of [
      ['p_value', filters.pValue],
      ['q_value', filters.qValue],
      ['correlation_low', filters.correlationLow],
      ['correlation_high', filters.correlationHigh],
      ['effect_low', filters.effectLow],
      ['effect_high', filters.effectHigh],
    ] as const) {
      if (value !== null && value !== undefined) {
        params = params.set(key, value);
      }
    }
    if (hasCutoffs(filters)) {
      params = params.set('threshold_mode', filters.thresholdMode);
    }
  }
  if (sort.by) {
    params = params.set('sort_by', sort.by).set('sort_order', sort.order);
  }
  return params;
}

// --- the URL, so a filtered search can be shared -------------------------------------------

const LIST_KEYS = { species: 'species', tiers: 'tier', scoreTypes: 'score' } as const;
const NUMBER_KEYS = {
  sizeMin: 'min_size',
  sizeMax: 'max_size',
  pValue: 'p',
  qValue: 'q',
  correlationLow: 'corr_low',
  correlationHigh: 'corr_high',
  effectLow: 'effect_low',
  effectHigh: 'effect_high',
} as const;

/** Router query parameters for the filters and sort; unset ones are `null`, which clears them. */
export function toQueryParams(filters: SearchFilters, sort: Sort): Record<string, string | null> {
  const params: Record<string, string | null> = {};
  for (const [key, name] of Object.entries(LIST_KEYS)) {
    const ids = filters[key as keyof typeof LIST_KEYS];
    params[name] = ids.length ? ids.join(',') : null;
  }
  for (const [key, name] of Object.entries(NUMBER_KEYS)) {
    const value = filters[key as keyof typeof NUMBER_KEYS];
    params[name] = value === null ? null : String(value);
  }
  params['gene'] = filters.gene.trim() || null;
  params['mode'] = filters.thresholdMode === 'first' ? 'first' : null;
  params['sort'] = sort.by;
  params['order'] = sort.by && sort.order === 'desc' ? 'desc' : null;
  return params;
}

/** The filters and sort in router query parameters; anything unreadable is left unset. */
export function fromQueryParams(params: Record<string, string | undefined>): { filters: SearchFilters; sort: Sort } {
  const filters = emptyFilters();
  for (const [key, name] of Object.entries(LIST_KEYS)) {
    filters[key as keyof typeof LIST_KEYS] = (params[name] ?? '')
      .split(',')
      .map(Number)
      .filter((id) => Number.isInteger(id) && id > 0);
  }
  for (const [key, name] of Object.entries(NUMBER_KEYS)) {
    const raw = params[name];
    const value = raw === undefined || raw === '' ? NaN : Number(raw);
    filters[key as keyof typeof NUMBER_KEYS] = Number.isFinite(value) ? value : null;
  }
  filters.gene = params['gene'] ?? '';
  filters.thresholdMode = params['mode'] === 'first' ? 'first' : 'only';
  const by = SORT_OPTIONS.some((option) => option.value === params['sort']) ? (params['sort'] as SortKey) : null;
  return { filters, sort: { by, order: params['order'] === 'desc' ? 'desc' : 'asc' } };
}

/** The cutoffs set, as "p-value ≤ 0.05 or correlation 0.3 to 1"; a gene set has one score type. */
function describeCutoffs(filters: SearchFilters): string {
  const parts: string[] = [];
  if (filters.pValue !== null) parts.push(`p-value ≤ ${filters.pValue}`);
  if (filters.qValue !== null) parts.push(`q-value ≤ ${filters.qValue}`);
  for (const [name, low, high] of [
    ['correlation', filters.correlationLow, filters.correlationHigh],
    ['effect', filters.effectLow, filters.effectHigh],
  ] as const) {
    if (low !== null && high !== null) parts.push(`${name} ${low} to ${high}`);
    else if (low !== null) parts.push(`${name} ≥ ${low}`);
    else if (high !== null) parts.push(`${name} ≤ ${high}`);
  }
  return parts.join(' or ');
}

/**
 * What a search returns, in words: always gene sets, matched by their text, by holding a gene
 * (with its score in range, if cutoffs are set), or both. Other filters only narrow it.
 */
export function describeSearch(text: string, filters: SearchFilters): string {
  const reasons: string[] = [];
  if (text.trim()) {
    reasons.push(`whose name, description, publication, ontology terms or genes match "${text.trim()}"`);
  }
  const gene = filters.gene.trim();
  if (gene) {
    const cutoffs = describeCutoffs(filters);
    if (!cutoffs) {
      reasons.push(`that contain ${gene}`);
    } else if (filters.thresholdMode === 'first') {
      reasons.push(`that contain ${gene}, those where its ${cutoffs} first`);
    } else {
      reasons.push(`that contain ${gene} with ${cutoffs}`);
    }
  }
  return reasons.length ? `Gene sets ${reasons.join(', and ')}` : '';
}

/** "Mus musculus", or the id when it is not one we name. */
export function speciesName(id: number | null | undefined): string {
  return SPECIES_OPTIONS.find((option) => option.id === id)?.label ?? (id ? `Species ${id}` : '');
}

export function scoreTypeName(id: number | null | undefined): string {
  return SCORE_TYPE_OPTIONS.find((option) => option.id === id)?.label ?? '';
}
