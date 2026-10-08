/**
 * Shaping each tool's output into what its chart draws.
 *
 * Pure functions, no D3 and no DOM: the ported tools return *data only* (legacy's SVG was
 * dropped -- G3-803), and the awkward part of every chart is turning that data into
 * marks, not drawing the marks. Keeping it here means it is unit-tested against real
 * tool outputs, and the components stay thin.
 */

// --- shared --------------------------------------------------------------------------

/** One line of a tooltip: a label and its value. */
export interface TooltipRow {
  label: string;
  value: string;
}

/** What a tooltip shows: a heading, label/value rows, and an optional closing note. */
export interface TooltipContent {
  title: string;
  rows?: TooltipRow[];
  note?: string;
}

/** How gene sets are labelled across every chart. */
export function genesetLabel(id: string | number): string {
  return `GS${id}`;
}

/** A p-value for display; very small values in exponent form, never a bare 0. */
export function formatP(p: number | null | undefined): string {
  if (p === null || p === undefined || Number.isNaN(p)) {
    return 'no p-value';
  }
  if (p === 0) {
    return '< 1e-300';
  }
  return p < 0.001 ? p.toExponential(1) : p.toFixed(3);
}

/**
 * An empirical p-value (from a sampled null distribution) for display.
 *
 * Unlike an exact p, a 0 here only means no sample was as extreme: it is bounded by the
 * number of samples, so it must not be shown as "< 1e-300". With `samples` known it is
 * shown as "< 1/samples"; without it, as below the distribution's resolution.
 */
export function formatEmpiricalP(p: number | null | undefined, samples?: number): string {
  if (p === 0) {
    return samples && samples > 0
      ? `< ${formatP(1 / samples)} (no sample as extreme)`
      : '≈ 0 (no sampled pair as similar)';
  }
  return formatP(p);
}

// --- UpSet -----------------------------------------------------------------------------

export interface UpSetBar {
  /** Gene set ids in this exclusive combination. */
  sets: string[];
  size: number;
}

export interface UpSetModel {
  sets: { id: string; size: number; unique: number }[];
  bars: UpSetBar[];
  /** Genes in any of the sets: the sum of every exclusive combination. */
  total: number;
  /** Combinations left out to keep the plot readable. */
  hidden: number;
}

/** Largest combinations first, capped; empty combinations are never drawn. */
export function upsetModel(
  genesetIds: (string | number)[],
  geneCounts: Record<string, number>,
  intersections: { geneset_ids: string[]; size: number }[],
  maxBars = 30,
): UpSetModel {
  const nonEmpty = intersections
    .filter((item) => item.size > 0)
    .map((item) => ({ sets: [...item.geneset_ids], size: item.size }))
    .sort((a, b) => b.size - a.size || a.sets.length - b.sets.length);
  const uniqueTo = (id: string) =>
    nonEmpty.find((bar) => bar.sets.length === 1 && bar.sets[0] === id)?.size ?? 0;
  return {
    sets: genesetIds.map((id) => ({
      id: String(id),
      size: geneCounts[String(id)] ?? 0,
      unique: uniqueTo(String(id)),
    })),
    bars: nonEmpty.slice(0, maxBars),
    total: nonEmpty.reduce((sum, bar) => sum + bar.size, 0),
    hidden: Math.max(0, nonEmpty.length - maxBars),
  };
}

// --- pairwise matrices (JaccardSimilarity, HyperGeometric) -----------------------------

export interface MatrixCell {
  row: string;
  col: string;
  /** Colour value; null cells are drawn blank (the diagonal, or no statistic). */
  value: number | null;
  /** Text inside the cell. */
  label: string;
  tooltip: TooltipContent;
}

export interface MatrixModel {
  ids: string[];
  cells: MatrixCell[];
  /** Colour scale bounds. */
  domain: [number, number];
  legend: string;
}

interface PairResult {
  i: number;
  j: number;
}

function mirrored<T extends PairResult>(
  ids: string[],
  results: T[],
  cell: (result: T, row: string, col: string) => MatrixCell,
  diagonal: (id: string) => MatrixCell,
): MatrixCell[] {
  const cells: MatrixCell[] = ids.map(diagonal);
  for (const result of results) {
    const a = ids[result.i];
    const b = ids[result.j];
    if (a === undefined || b === undefined) {
      continue;
    }
    cells.push(cell(result, a, b), cell(result, b, a));
  }
  return cells;
}

const sameSet = (id: string): MatrixCell => ({
  row: id,
  col: id,
  value: null,
  label: '',
  tooltip: { title: genesetLabel(id), note: 'The same gene set.' },
});

export interface JaccardSimilarityOutput {
  geneset_ids: string[];
  p_value_threshold: number;
  results: {
    i: number;
    j: number;
    jaccard: number;
    p_value: number | null;
    intersection: number;
    only_i: number;
    only_j: number;
  }[];
}

/** Jaccard index per pair, coloured 0..1; the p-value goes in the tooltip. */
export function jaccardMatrix(output: JaccardSimilarityOutput): MatrixModel {
  const ids = output.geneset_ids.map(String);
  const threshold = output.p_value_threshold;
  const cells = mirrored(
    ids,
    output.results,
    (r, row, col) => {
      // The pair's counts are oriented i -> j; a mirrored cell swaps them back.
      const [onlyRow, onlyCol] = row === ids[r.i] ? [r.only_i, r.only_j] : [r.only_j, r.only_i];
      const significant = r.p_value !== null && r.p_value <= threshold;
      return {
        row,
        col,
        value: r.jaccard,
        label: r.jaccard.toFixed(2),
        tooltip: {
          title: `${genesetLabel(row)} vs ${genesetLabel(col)}`,
          rows: [
            { label: 'Jaccard index', value: r.jaccard.toFixed(3) },
            { label: 'p-value', value: r.p_value === null ? 'none' : formatEmpiricalP(r.p_value) },
            ...(r.p_value === null
              ? []
              : [{ label: `Significant at p ≤ ${threshold}`, value: significant ? 'yes' : 'no' }]),
            { label: 'Shared genes', value: String(r.intersection) },
            { label: `Only in ${genesetLabel(row)}`, value: String(onlyRow) },
            { label: `Only in ${genesetLabel(col)}`, value: String(onlyCol) },
          ],
          note:
            r.p_value === null
              ? 'No null distribution covers these two set sizes, so there is no p-value.'
              : undefined,
        },
      };
    },
    sameSet,
  );
  return { ids, cells, domain: [0, 1], legend: 'Jaccard index' };
}

export interface HyperGeometricOutput {
  geneset_ids: string[];
  results: {
    i: number;
    j: number;
    upper_tail: number;
    lower_tail?: number;
    two_tailed?: number;
    odds_ratio: number | null;
  }[];
}

/** Smallest representable p, so -log10 stays finite for an exact 0. */
const P_FLOOR = 1e-300;

/** Over-representation per pair as -log10(upper-tail p): larger is more significant. */
export function hypergeometricMatrix(output: HyperGeometricOutput): MatrixModel {
  const ids = output.geneset_ids.map(String);
  const cells = mirrored(
    ids,
    output.results,
    (r, row, col) => {
      const score = -Math.log10(Math.max(r.upper_tail, P_FLOOR));
      const rows: TooltipRow[] = [
        { label: 'Upper-tail p (more shared than chance)', value: formatP(r.upper_tail) },
      ];
      if (r.lower_tail !== undefined) {
        rows.push({ label: 'Lower-tail p (fewer shared)', value: formatP(r.lower_tail) });
      }
      if (r.two_tailed !== undefined) {
        rows.push({ label: 'Two-tailed p', value: formatP(r.two_tailed) });
      }
      rows.push({
        label: 'Odds ratio',
        value: r.odds_ratio === null ? 'undefined' : r.odds_ratio.toFixed(2),
      });
      return {
        row,
        col,
        value: score,
        label: formatP(r.upper_tail),
        tooltip: { title: `${genesetLabel(row)} vs ${genesetLabel(col)}`, rows },
      };
    },
    sameSet,
  );
  const max = Math.max(1, ...cells.map((c) => c.value ?? 0));
  return { ids, cells, domain: [0, max], legend: '−log10 upper-tail p' };
}

// --- JaccardClustering -------------------------------------------------------------------

export interface ClusterNode {
  geneset_id?: string | null;
  distance?: number | null;
  children?: ClusterNode[];
}

export interface DendrogramNode {
  name: string;
  /** Merge height; leaves sit at 0. */
  height: number;
  children?: DendrogramNode[];
}

/** The tool's tree, with each merge's distance as its height and leaves at 0. */
export function dendrogramModel(tree: ClusterNode | null | undefined): DendrogramNode | null {
  if (!tree) {
    return null;
  }
  const walk = (node: ClusterNode): DendrogramNode => {
    const children = node.children ?? [];
    if (children.length === 0) {
      return { name: genesetLabel(node.geneset_id ?? '?'), height: 0 };
    }
    return { name: '', height: node.distance ?? 0, children: children.map(walk) };
  };
  return walk(tree);
}

// --- DBSCAN ----------------------------------------------------------------------------

export interface PackNode {
  name: string;
  value?: number;
  children?: PackNode[];
}

/** Clusters as groups of genes, for circle packing. */
export function dbscanModel(output: { ran: boolean; clusters: string[][] }): PackNode | null {
  if (!output.ran || output.clusters.length === 0) {
    return null;
  }
  return {
    name: 'clusters',
    children: output.clusters.map((genes, index) => ({
      name: `Cluster ${index + 1} (${genes.length} genes)`,
      children: genes.map((gene) => ({ name: gene, value: 1 })),
    })),
  };
}

// --- BooleanAlgebra --------------------------------------------------------------------

/** A row of `bool_results`: [gene id, identifier, species id, gene set id]. */
type BooleanRow = [number, string, number, number];

export interface BooleanAlgebraOutput {
  relation: string;
  at_least: number;
  geneset_ids: number[];
  bool_results: Record<string, BooleanRow[]>;
  circle_groups?: Record<string, number[]> | null;
  intersect_results?: Record<string, Record<string, BooleanRow[]>> | null;
  bool_except?: Record<string, Record<string, BooleanRow[]>> | null;
}

export interface BooleanGene {
  key: string;
  label: string;
  /** Distinct gene sets the gene belongs to. */
  sets: number[];
}

export interface BooleanModel {
  relation: string;
  atLeast: number;
  sets: { id: number; size: number }[];
  /** Genes in the relation's answer, exactly as the tool returned it. */
  result: BooleanGene[];
  /**
   * For an intersection, answer genes found in fewer *distinct* gene sets than `atLeast`.
   * Non-zero means the tool counted identifier rows rather than gene sets (a gene listed
   * by symbol and by UniGene id in one set passes "in at least 2"); shown, not hidden.
   */
  belowThreshold: number;
  /** Exact membership combinations across every gene, largest first. */
  combinations: { sets: number[]; size: number }[];
}

/** A UniGene cluster id such as `Mm.334198`: an identifier, not a name to show. */
const UNIGENE = /^[A-Z][a-z]\.\d+$/;

function geneLabel(rows: BooleanRow[] | undefined, key: string): string {
  const identifiers = (rows ?? []).map((row) => String(row[1]));
  return identifiers.find((id) => !UNIGENE.test(id)) ?? identifiers[0] ?? key;
}

/**
 * The tool's per-gene rows, reduced to one entry per gene with its *distinct* gene sets.
 *
 * `circle_groups` repeats a gene set once per identifier the gene has in it (symbol and
 * UniGene id, say), so counting its entries over-counts membership; that is why a gene
 * found in one gene set could look like it was in two.
 */
export function booleanModel(output: BooleanAlgebraOutput): BooleanModel {
  const groups = output.circle_groups ?? {};
  const genes = new Map<string, BooleanGene>();
  for (const [key, rows] of Object.entries(output.bool_results)) {
    const fromGroups = groups[key] ?? rows.map((row) => row[3]);
    genes.set(key, {
      key,
      label: geneLabel(rows, key),
      sets: [...new Set(fromGroups.map(Number))].sort((a, b) => a - b),
    });
  }

  const relation = output.relation.toLowerCase();
  const keysOf = (nested?: Record<string, Record<string, BooleanRow[]>> | null) =>
    new Set(Object.values(nested ?? {}).flatMap((bySpecies) => Object.keys(bySpecies)));
  let resultKeys: Set<string>;
  if (relation === 'intersection') {
    resultKeys = keysOf(output.intersect_results);
  } else if (relation === 'except') {
    resultKeys = keysOf(output.bool_except);
  } else {
    resultKeys = new Set(genes.keys());
  }

  const sizes = new Map<number, number>();
  const combos = new Map<string, number>();
  for (const gene of genes.values()) {
    gene.sets.forEach((id) => sizes.set(id, (sizes.get(id) ?? 0) + 1));
    const signature = gene.sets.join(',');
    combos.set(signature, (combos.get(signature) ?? 0) + 1);
  }

  const result = [...resultKeys]
    .map((key) => genes.get(key) ?? { key, label: key, sets: [] })
    .sort((a, b) => b.sets.length - a.sets.length || a.label.localeCompare(b.label));

  return {
    relation: output.relation,
    atLeast: output.at_least,
    sets: output.geneset_ids.map((id) => ({ id, size: sizes.get(id) ?? 0 })),
    result,
    belowThreshold:
      relation === 'intersection'
        ? result.filter((gene) => gene.sets.length < output.at_least).length
        : 0,
    combinations: [...combos.entries()]
      .map(([signature, size]) => ({
        sets: signature ? signature.split(',').map(Number) : [],
        size,
      }))
      .sort((a, b) => b.size - a.size),
  };
}

// --- Venn geometry (area-proportional, 2 or 3 circles) ---------------------------------

/** Area of the lens where circles of radius r1, r2 at centre distance d overlap. */
export function lensArea(r1: number, r2: number, d: number): number {
  if (d >= r1 + r2) {
    return 0;
  }
  if (d <= Math.abs(r1 - r2)) {
    return Math.PI * Math.min(r1, r2) ** 2;
  }
  const a = r1 * r1 * Math.acos((d * d + r1 * r1 - r2 * r2) / (2 * d * r1));
  const b = r2 * r2 * Math.acos((d * d + r2 * r2 - r1 * r1) / (2 * d * r2));
  const c = 0.5 * Math.sqrt((-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2));
  return a + b - c;
}

/** The centre distance at which two circles overlap by `overlap` area (bisection). */
export function distanceForOverlap(r1: number, r2: number, overlap: number): number {
  if (overlap <= 0) {
    return r1 + r2;
  }
  let lo = Math.abs(r1 - r2);
  let hi = r1 + r2;
  if (overlap >= lensArea(r1, r2, lo)) {
    return lo;
  }
  for (let step = 0; step < 60; step++) {
    const mid = (lo + hi) / 2;
    if (lensArea(r1, r2, mid) > overlap) {
      lo = mid;
    } else {
      hi = mid;
    }
  }
  return (lo + hi) / 2;
}

export interface VennCircle {
  id: number;
  x: number;
  y: number;
  r: number;
  size: number;
}

/**
 * Circles whose areas match the set sizes and whose pairwise overlaps match the shared
 * counts. Exact for two sets; for three, each pair's distance is exact and the third
 * circle is placed by triangulation, clamped where the three distances cannot all hold.
 * More than three sets cannot be drawn faithfully as circles -- callers fall back to the
 * combination table.
 */
export function vennLayout(
  sets: { id: number; size: number }[],
  shared: (a: number, b: number) => number,
): VennCircle[] | null {
  if (sets.length < 2 || sets.length > 3 || sets.some((s) => s.size <= 0)) {
    return null;
  }
  const radius = (size: number) => Math.sqrt(size / Math.PI);
  const [a, b, c] = sets;
  const ra = radius(a.size);
  const rb = radius(b.size);
  const dab = distanceForOverlap(ra, rb, shared(a.id, b.id));
  const circles: VennCircle[] = [
    { id: a.id, x: 0, y: 0, r: ra, size: a.size },
    { id: b.id, x: dab, y: 0, r: rb, size: b.size },
  ];
  if (c) {
    const rc = radius(c.size);
    const dac = distanceForOverlap(ra, rc, shared(a.id, c.id));
    const dbc = distanceForOverlap(rb, rc, shared(b.id, c.id));
    const cos = dab > 0 ? (dab * dab + dac * dac - dbc * dbc) / (2 * dab * dac || 1) : 0;
    const angle = Math.acos(Math.max(-1, Math.min(1, cos)));
    circles.push({
      id: c.id,
      x: dac * Math.cos(angle),
      y: dac * Math.sin(angle),
      r: rc,
      size: c.size,
    });
  }
  return circles;
}

// --- MSET ------------------------------------------------------------------------------

export interface MsetModel {
  /** Share of random trials per intersection size. */
  bins: { overlap: number; share: number }[];
  observed: number | null;
  pValue: string;
  trials: string;
  summary: { label: string; value: string }[];
}

export function msetModel(output: {
  intersect_genes: string[];
  mset_data: Record<string, string>;
  mset_hist: Record<string, string>;
}): MsetModel {
  const observed = Number.parseInt(output.mset_data['List 1/2 Intersect'] ?? '', 10);
  const rawP = output.mset_data['P-Value'];
  const trials = Number.parseInt(output.mset_data['Num Trials'] ?? '', 10);
  const pValue =
    rawP === undefined
      ? 'unknown'
      : formatEmpiricalP(Number(rawP), Number.isFinite(trials) ? trials : undefined);
  return {
    bins: Object.entries(output.mset_hist)
      .map(([overlap, share]) => ({ overlap: Number(overlap), share: Number(share) }))
      .filter((bin) => Number.isFinite(bin.overlap) && Number.isFinite(bin.share))
      .sort((a, b) => a.overlap - b.overlap),
    observed: Number.isFinite(observed) ? observed : output.intersect_genes.length,
    pValue,
    trials: output.mset_data['Num Trials'] ?? 'unknown',
    summary: Object.entries(output.mset_data).map(([label, value]) => ({ label, value })),
  };
}

// --- PhenomeMap ------------------------------------------------------------------------

export interface PhenomeMapNode {
  id: number;
  genesets: string[];
  genes: string[];
  depth: number;
  displayed?: boolean;
  emphasize?: boolean;
  children?: { target: number; score: number }[];
}

export interface GraphElement {
  group: 'nodes' | 'edges';
  data: Record<string, unknown>;
  position?: { x: number; y: number };
}

/** Spacing of the layered layout, in Cytoscape model units. */
const COLUMN = 120;
const ROW = 130;

/**
 * Positions for a layered drawing: one row per `depth` the tool assigned, ordered within
 * each row by the mean position of the node's parents so links cross less.
 *
 * Uses the tool's own levels rather than letting a layout infer them. Inferred levels
 * follow the *shortest* path from the top, while the tool's follow the longest, so an
 * inferred layout put children level with their own parents and drew links sideways.
 * Every link in a PhenomeMap result points to a deeper level, so these rows never do.
 */
export function phenomeMapPositions(nodes: PhenomeMapNode[]): Map<number, { x: number; y: number }> {
  const parentsOf = new Map<number, number[]>();
  for (const node of nodes) {
    for (const link of node.children ?? []) {
      parentsOf.set(link.target, [...(parentsOf.get(link.target) ?? []), node.id]);
    }
  }
  const byDepth = new Map<number, PhenomeMapNode[]>();
  for (const node of nodes) {
    byDepth.set(node.depth, [...(byDepth.get(node.depth) ?? []), node]);
  }
  const positions = new Map<number, { x: number; y: number }>();
  for (const [depth, row] of [...byDepth.entries()].sort(([a], [b]) => a - b)) {
    const mean = (node: PhenomeMapNode) => {
      const xs = (parentsOf.get(node.id) ?? [])
        .map((id) => positions.get(id)?.x)
        .filter((x): x is number => x !== undefined);
      return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0;
    };
    row.sort((a, b) => mean(a) - mean(b) || a.id - b.id);
    row.forEach((node, index) => {
      positions.set(node.id, { x: (index - (row.length - 1) / 2) * COLUMN, y: depth * ROW });
    });
  }
  return positions;
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/**
 * Bicliques as graph nodes, positioned in layers and linked parent to child, for
 * Cytoscape. Nodes the tool hid (bootstrap reduction, level cut) are left out with the
 * links that touch them.
 */
export function phenomeMapElements(output: { nodes: PhenomeMapNode[] }): GraphElement[] {
  const shown = output.nodes.filter((node) => node.displayed !== false);
  const ids = new Set(shown.map((node) => node.id));
  const positions = phenomeMapPositions(shown);
  // The tool flags *every* node when no emphasis genes were given, so a flag on all of them
  // singles nothing out; only draw it when it actually distinguishes some.
  const emphasisMeans = shown.some((node) => node.emphasize) && shown.some((node) => !node.emphasize);
  const nodes: GraphElement[] = shown.map((node) => ({
    group: 'nodes',
    position: positions.get(node.id),
    data: {
      id: `n${node.id}`,
      label: `${plural(node.genesets.length, 'set', 'sets')} · ${plural(node.genes.length, 'gene', 'genes')}`,
      genesets: node.genesets,
      genes: node.genes,
      depth: node.depth,
      emphasize: emphasisMeans && !!node.emphasize,
      weight: node.genes.length,
    },
  }));
  const edges: GraphElement[] = shown.flatMap((node) =>
    (node.children ?? [])
      .filter((link) => ids.has(link.target))
      .map((link) => ({
        group: 'edges' as const,
        data: {
          id: `e${node.id}-${link.target}`,
          source: `n${node.id}`,
          target: `n${link.target}`,
          score: link.score,
        },
      })),
  );
  return [...nodes, ...edges];
}

// --- Combine ---------------------------------------------------------------------------

export interface CombineModel {
  columns: { id: string; label: string }[];
  rows: { gene: string; members: Record<string, boolean>; count: number }[];
}

/**
 * The gene x gene set membership matrix. Each matrix row is keyed by gene set id, with
 * key `0` holding the gene's display identifier.
 */
export function combineModel(output: {
  geneset_ids: (number | string)[];
  matrix: Record<string, Record<string, unknown>>;
  gslabels?: Record<string, string>;
}): CombineModel {
  const columns = output.geneset_ids.map((id) => ({
    id: String(id),
    label: output.gslabels?.[String(id)] || genesetLabel(id),
  }));
  const rows = Object.entries(output.matrix).map(([geneId, cells]) => {
    const members: Record<string, boolean> = {};
    for (const column of columns) {
      members[column.id] = !!cells[column.id];
    }
    return {
      gene: String(cells['0'] ?? geneId),
      members,
      count: Object.values(members).filter(Boolean).length,
    };
  });
  rows.sort((a, b) => b.count - a.count || a.gene.localeCompare(b.gene));
  return { columns, rows };
}
