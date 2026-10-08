/**
 * Shapes ABBA's result (`POST /tools/abba`) for legacy's four result sections: run
 * information, seed genes, the top gene sets and the top genes.
 *
 * Kept apart from `models.ts`: ABBA is a gene-centred search, not a gene-set analysis, so it
 * shares none of the other tools' shapes. Colours follow legacy's `ABBA_result.html` and
 * `search.css` so the page reads the same.
 */

import { TooltipContent } from './models';

// --- the API contract ---------------------------------------------------------------------

export interface AbbaParameters {
  include_homology: boolean;
  /** `null` is legacy's "Auto". */
  min_genes: number | null;
  min_genesets: number | null;
  tiers: number[];
  /** `null` means every species: not restricted. */
  species_ids: number[] | null;
}

export interface AbbaSeedGene {
  ode_gene_id: number;
  symbol: string;
  species_id: number | null;
  species: string | null;
}

export interface AbbaGeneset {
  gs_id: number;
  name: string;
  abbreviation?: string | null;
  description?: string | null;
  matches: number;
  tier: number | null;
  species_id: number | null;
  /** The attribution's abbreviation, as the database holds it: "KEGG", "CTD", "MESH"... */
  attribution?: string | null;
  gene_count: number;
}

export interface AbbaGene {
  ode_gene_id: number;
  symbol: string;
  symbols: string[];
  species_id: number;
  species: string;
  occurrences: number;
  tier_counts: Record<string, number>;
  species_counts: Record<string, number>;
}

export interface AbbaResult {
  tool: 'abba';
  parameters: AbbaParameters;
  available_genes: number;
  available_genesets: number;
  input_species: string[];
  seed_genes: AbbaSeedGene[];
  genesets: AbbaGeneset[];
  genes: AbbaGene[];
  max_occurrences: number;
  species: Record<string, string>;
  /** Tier id -> the database's name, e.g. "Tier I - Public Resource". */
  tiers: Record<string, string>;
}

// --- the search form ----------------------------------------------------------------------

/**
 * The seed genes as typed: one per line, or separated by commas, semicolons or spaces.
 * Duplicates are dropped case-insensitively (the API matches symbols that way), keeping
 * the first spelling.
 */
export function parseGeneList(text: string): string[] {
  const seen = new Set<string>();
  const genes: string[] = [];
  for (const token of text.split(/[\s,;]+/)) {
    const gene = token.trim();
    if (gene && !seen.has(gene.toLowerCase())) {
      seen.add(gene.toLowerCase());
      genes.push(gene);
    }
  }
  return genes;
}

// --- colours and labels -------------------------------------------------------------------

export interface TileStyle {
  background: string;
  border: string;
}

/** Legacy's seed tile colours, by species name (ColorBrewer Pastel1, with darker borders). */
const SPECIES_TILES: Record<string, TileStyle> = {
  'Drosophila melanogaster': { background: '#ccebc5', border: '#66855F' },
  'Rattus norvegicus': { background: '#fbb4ae', border: '#954E48' },
  'Homo sapiens': { background: '#decbe4', border: '#78657E' },
  'Mus musculus': { background: '#b3cde3', border: '#4D677D' },
  'Macaca mulatta': { background: '#fed9a6', border: '#987340' },
  'Gallus gallus': { background: '#ffffcc', border: '#999966' },
  'Canis familiaris': { background: '#e5d8bd', border: '#7f7257' },
  'Danio rerio': { background: '#fddaec', border: '#977486' },
};
/** Every other species -- legacy left them white. */
const OTHER_TILE: TileStyle = { background: '#ffffff', border: '#8C8C8C' };

/** A species' tile colours. Text on them is always dark: every background is pale. */
export function speciesTile(species: string | null | undefined): TileStyle {
  if (!species) {
    return OTHER_TILE;
  }
  const match = Object.keys(SPECIES_TILES).find(
    (name) => name.toLowerCase() === species.toLowerCase(),
  );
  return match ? SPECIES_TILES[match] : OTHER_TILE;
}

/** The short names legacy's badges used ("Human", not "Homo sapiens"). */
const COMMON_NAMES: Record<string, string> = {
  'mus musculus': 'Mouse',
  'homo sapiens': 'Human',
  'rattus norvegicus': 'Rat',
  'danio rerio': 'Zebrafish',
  'drosophila melanogaster': 'Fly',
  'macaca mulatta': 'Monkey',
  'caenorhabditis elegans': 'Worm',
  'saccharomyces cerevisiae': 'Yeast',
  'gallus gallus': 'Chicken',
  'canis familiaris': 'Dog',
};

export function speciesCommonName(species: string | null | undefined): string {
  if (!species) {
    return 'Unknown';
  }
  return COMMON_NAMES[species.toLowerCase()] ?? species;
}

/**
 * Bar colours for the "gene sets by species" sparkline: legacy's `hom_colors`, indexed by
 * species id - 1 (there is no species 7, hence the gap).
 */
const SPECIES_BAR_COLORS = [
  '#58D87E', '#588C7E', '#F2E394', '#1F77B4', '#F2AE72',
  '#F2AF28', '#9CA3AF', '#D96459', '#D93459', '#5E228B', '#698FC6',
];

export function speciesBarColor(speciesId: number): string {
  return SPECIES_BAR_COLORS[speciesId - 1] ?? '#9CA3AF';
}

/** The tier sparkline's colour, legacy's dark green. */
export const TIER_BAR_COLOR = '#006644';

/** Legacy's tier badge colours (`search.css` .tier1 - .tier5). */
const TIER_BADGES: Record<number, TileStyle> = {
  1: { background: '#ffc477', border: '#eeb44f' },
  2: { background: '#dfbdfa', border: '#c584f3' },
  3: { background: '#fa665a', border: '#d83526' },
  4: { background: '#9dce2c', border: '#83c41a' },
  5: { background: '#63b8ee', border: '#3866a3' },
};

export function tierBadge(tier: number | null | undefined): TileStyle {
  return (tier && TIER_BADGES[tier]) || OTHER_TILE;
}

const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V'];

/**
 * A tier's full name, e.g. "Tier II - Pro-curated", from the API's labels when it sent them,
 * else "Tier II".
 */
export function tierName(tier: number | null | undefined, labels: Record<string, string> = {}): string {
  if (tier === null || tier === undefined) {
    return 'No tier';
  }
  return labels[String(tier)] ?? `Tier ${ROMAN[tier] ?? tier}`;
}

/** A tier's badge text, "Tier II": the full name up to its " - " description. */
export function tierLabel(tier: number | null | undefined, labels: Record<string, string> = {}): string {
  return tierName(tier, labels).split(' - ')[0];
}

// --- run information ----------------------------------------------------------------------

export interface InfoRow {
  label: string;
  value: string;
}

/** Legacy's "Run Information" panel, in its order and wording. */
export function abbaRunInfo(result: AbbaResult, ranAt?: Date): InfoRow[] {
  const p = result.parameters;
  const restricted = p.species_ids?.length
    ? p.species_ids.map((id) => result.species[String(id)] ?? `species ${id}`).join(', ')
    : 'No';
  const rows: InfoRow[] = [
    { label: 'Include homology', value: p.include_homology ? 'Yes' : 'No' },
    { label: 'Minimum genes', value: p.min_genes === null ? 'Auto' : String(p.min_genes) },
    { label: 'Minimum gene sets', value: p.min_genesets === null ? 'Auto' : String(p.min_genesets) },
    { label: 'Curation tiers', value: `IN (${[...p.tiers].sort((a, b) => a - b).join(',')})` },
    { label: 'Restricted to species', value: restricted },
  ];
  if (ranAt) {
    rows.push({ label: 'Date', value: ranAt.toLocaleString() });
  }
  rows.push(
    { label: 'Available genes', value: result.available_genes.toLocaleString() },
    { label: 'Available gene sets', value: result.available_genesets.toLocaleString() },
  );
  return rows;
}

// --- gene sets ----------------------------------------------------------------------------

export type GenesetSort = 'none' | 'tier' | 'species' | 'attribution';

export const GENESET_SORTS: { value: GenesetSort; label: string }[] = [
  { value: 'none', label: 'None' },
  { value: 'tier', label: 'Sort by tier' },
  { value: 'species', label: 'Sort by species' },
  { value: 'attribution', label: 'Sort by attribution' },
];

/**
 * The gene sets in the chosen order. "None" is the API's order (most matches first); the
 * others group by that field and keep the API's order within a group. Missing values sort
 * last. Legacy showed this dropdown but never wired it.
 */
export function sortGenesets(
  genesets: AbbaGeneset[],
  by: GenesetSort,
  species: Record<string, string> = {},
): AbbaGeneset[] {
  if (by === 'none') {
    return [...genesets];
  }
  const key = (g: AbbaGeneset): string | number | null => {
    switch (by) {
      case 'tier':
        return g.tier ?? null;
      case 'species':
        return g.species_id === null ? null : (species[String(g.species_id)] ?? String(g.species_id));
      case 'attribution':
        return g.attribution || null;
    }
  };
  return genesets
    .map((geneset, index) => ({ geneset, index, value: key(geneset) }))
    .sort((a, b) => {
      if (a.value === b.value) {
        return a.index - b.index;
      }
      if (a.value === null) {
        return 1;
      }
      if (b.value === null) {
        return -1;
      }
      const order =
        typeof a.value === 'number' && typeof b.value === 'number'
          ? a.value - b.value
          : String(a.value).localeCompare(String(b.value));
      return order || a.index - b.index;
    })
    .map((entry) => entry.geneset);
}

// --- genes --------------------------------------------------------------------------------

export interface SparkBar {
  id: number;
  label: string;
  count: number;
  /** 0..1 of the sparkline's height. */
  height: number;
  color: string;
}

/** One bar per tier, 1 to 5, scaled to the gene's largest tier. */
export function tierSparkline(gene: AbbaGene, labels: Record<string, string> = {}): SparkBar[] {
  const counts = [1, 2, 3, 4, 5].map((tier) => gene.tier_counts[String(tier)] ?? 0);
  const max = Math.max(...counts, 0);
  return counts.map((count, index) => ({
    id: index + 1,
    label: tierName(index + 1, labels),
    count,
    height: max > 0 ? count / max : 0,
    color: TIER_BAR_COLOR,
  }));
}

/**
 * One bar per species (all of them, so columns line up down the table), log-scaled as
 * legacy's was: one species can hold thousands of a gene's gene sets and another a handful,
 * and on a linear scale the handful vanish. Species 0 ("all") is not a species.
 */
export function speciesSparkline(gene: AbbaGene, species: Record<string, string>): SparkBar[] {
  const ids = Object.keys(species)
    .map(Number)
    .filter((id) => id > 0)
    .sort((a, b) => a - b);
  const counts = ids.map((id) => gene.species_counts[String(id)] ?? 0);
  const maxLog = Math.log10(Math.max(...counts, 0) + 1);
  return ids.map((id, index) => ({
    id,
    label: species[String(id)],
    count: counts[index],
    height: maxLog > 0 ? Math.log10(counts[index] + 1) / maxLog : 0,
    color: speciesBarColor(id),
  }));
}

/** A sparkline's bars as tooltip content, for keyboard users who cannot hover each bar. */
export function sparklineSummary(title: string, bars: SparkBar[]): TooltipContent {
  return {
    title,
    rows: bars.map((bar) => ({ label: bar.label, value: bar.count.toLocaleString() })),
  };
}

/** How full a gene's occurrence bar is, against the largest. */
export function occurrenceFraction(gene: AbbaGene, maxOccurrences: number): number {
  return maxOccurrences > 0 ? Math.min(1, gene.occurrences / maxOccurrences) : 0;
}

/** Every symbol of a gene, the preferred one first, without repeats. */
export function geneSymbols(gene: AbbaGene): string[] {
  return [...new Set([gene.symbol, ...(gene.symbols ?? [])].filter(Boolean))];
}

function csvField(value: string | number): string {
  const text = String(value);
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** The chosen genes as CSV: what "Add genes to gene set" would have taken in legacy. */
export function genesCsv(genes: AbbaGene[]): string {
  const header = ['symbol', 'species', 'gene_sets', 'other_symbols'];
  const rows = genes.map((gene) => [
    gene.symbol,
    gene.species,
    gene.occurrences,
    geneSymbols(gene)
      .filter((symbol) => symbol !== gene.symbol)
      .join(' '),
  ]);
  return [header, ...rows].map((row) => row.map(csvField).join(',')).join('\n') + '\n';
}
