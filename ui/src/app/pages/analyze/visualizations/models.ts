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
      : '≈ 0 (no sample as extreme)';
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
      // 0 is not a tiny p: the tool returns 0.0 exactly when no null distribution covers the
      // pair (`empirical_p_value`), and a computed p is never 0 because it counts the
      // observation itself. So 0 means "no p-value", and must never read as significant.
      const hasP = r.p_value !== null && r.p_value > 0;
      const significant = hasP && (r.p_value as number) <= threshold;
      return {
        row,
        col,
        value: r.jaccard,
        label: r.jaccard.toFixed(2),
        tooltip: {
          title: `${genesetLabel(row)} vs ${genesetLabel(col)}`,
          rows: [
            { label: 'Jaccard index', value: r.jaccard.toFixed(3) },
            { label: 'p-value', value: hasP ? formatP(r.p_value) : 'none' },
            ...(hasP
              ? [{ label: `Significant at p ≤ ${threshold}`, value: significant ? 'yes' : 'no' }]
              : []),
            { label: 'Shared genes', value: String(r.intersection) },
            { label: `Only in ${genesetLabel(row)}`, value: String(onlyRow) },
            { label: `Only in ${genesetLabel(col)}`, value: String(onlyCol) },
          ],
          note: hasP
            ? undefined
            : 'No null distribution covers these two set sizes, so there is no p-value.',
        },
      };
    },
    sameSet,
  );
  return { ids, cells, domain: [0, 1], legend: 'Jaccard index' };
}

// --- JaccardSimilarity: the grid of pairwise Venn diagrams ------------------------------

export interface VennGridCircle {
  /** Centre and radius in a unit cell: (0, 0) top left, (1, 1) bottom right. */
  cx: number;
  cy: number;
  r: number;
  /** Which gene set it stands for: the cell's row set or its column set. */
  role: 'row' | 'col' | 'same';
}

export interface VennGridCell {
  row: string;
  col: string;
  diagonal: boolean;
  rowSize: number;
  colSize: number;
  shared: number;
  onlyRow: number;
  onlyCol: number;
  jaccard: number;
  /** The pair's p-value, or null when there is none (see `jaccardMatrix`). */
  p: number | null;
  circles: VennGridCircle[];
  /** The text legacy printed in each cell: counts, J, p. */
  lines: string[];
  tooltip: TooltipContent;
}

export interface VennGridModel {
  ids: string[];
  sizes: Record<string, number>;
  cells: VennGridCell[];
  /** The threshold the run was made with, which the grid starts from. */
  threshold: number;
}

/** p-value thresholds offered on the grid; legacy's list for JaccardSimilarity. */
export const P_THRESHOLDS = [1.0, 0.5, 0.1, 0.05, 0.01];

/**
 * Two circles in a unit cell, areas proportional to the set sizes and the lens to the shared
 * genes, scaled per cell to fill it -- as legacy did, so a cell compares its own two sets,
 * not sizes across cells.
 */
function pairCircles(rowSize: number, colSize: number, shared: number): VennGridCircle[] {
  const r1 = Math.sqrt(Math.max(rowSize, 0) / Math.PI);
  const r2 = Math.sqrt(Math.max(colSize, 0) / Math.PI);
  if (r1 === 0 && r2 === 0) {
    return [];
  }
  const d = distanceForOverlap(r1, r2, shared);
  const left = Math.min(-r1, d - r2);
  const right = Math.max(r1, d + r2);
  const scale = 0.84 / Math.max(right - left, 2 * Math.max(r1, r2));
  const shift = 0.5 - ((left + right) / 2) * scale;
  return [
    { cx: shift, cy: 0.5, r: r1 * scale, role: 'row' as const },
    { cx: shift + d * scale, cy: 0.5, r: r2 * scale, role: 'col' as const },
  ].filter((circle) => circle.r > 0);
}

/**
 * Legacy JaccardSimilarity's main view: an N x N grid with a two-set Venn diagram per pair.
 * Row i is gene set i, column j gene set j; the diagonal is each set against itself.
 *
 * Set sizes are not in the output directly; each comes from any pair it is in (shared +
 * only-in-it), which every pair agrees on.
 */
export function jaccardVennGrid(output: JaccardSimilarityOutput): VennGridModel {
  const ids = output.geneset_ids.map(String);
  const sizes: Record<string, number> = Object.fromEntries(ids.map((id) => [id, 0]));
  for (const r of output.results) {
    const a = ids[r.i];
    const b = ids[r.j];
    if (a !== undefined) sizes[a] = r.intersection + r.only_i;
    if (b !== undefined) sizes[b] = r.intersection + r.only_j;
  }
  const byPair = new Map<string, JaccardSimilarityOutput['results'][number]>();
  for (const r of output.results) {
    byPair.set(`${r.i},${r.j}`, r);
    byPair.set(`${r.j},${r.i}`, r);
  }
  const cells: VennGridCell[] = [];
  ids.forEach((row, i) => {
    ids.forEach((col, j) => {
      if (i === j) {
        const size = sizes[row];
        cells.push({
          row,
          col,
          diagonal: true,
          rowSize: size,
          colSize: size,
          shared: size,
          onlyRow: 0,
          onlyCol: 0,
          jaccard: 1,
          p: null,
          circles: size > 0 ? [{ cx: 0.5, cy: 0.5, r: 0.38, role: 'same' }] : [],
          lines: [`(${size})`],
          tooltip: {
            title: genesetLabel(row),
            rows: [{ label: 'Genes', value: String(size) }],
            note: 'The same gene set on both axes.',
          },
        });
        return;
      }
      const r = byPair.get(`${i},${j}`);
      if (!r) {
        return;
      }
      // Counts are oriented i -> j in the output; a cell below the diagonal swaps them.
      const [onlyRow, onlyCol] = r.i === i ? [r.only_i, r.only_j] : [r.only_j, r.only_i];
      // As in `jaccardMatrix`: 0 means no null distribution covered the pair, not a tiny p.
      const p = r.p_value !== null && r.p_value > 0 ? r.p_value : null;
      const pText = p === null ? 'none' : formatP(p);
      const lines =
        r.intersection === 0
          ? [`(${onlyRow})  (${onlyCol})`]
          : [`(${onlyRow} ${r.intersection} ${onlyCol})`, `J = ${r.jaccard.toFixed(3)}`, `p = ${pText}`];
      cells.push({
        row,
        col,
        diagonal: false,
        rowSize: sizes[row],
        colSize: sizes[col],
        shared: r.intersection,
        onlyRow,
        onlyCol,
        jaccard: r.jaccard,
        p,
        circles: pairCircles(sizes[row], sizes[col], r.intersection),
        lines,
        tooltip: {
          title: `${genesetLabel(row)} (row) vs ${genesetLabel(col)} (column)`,
          rows: [
            { label: 'Shared genes', value: String(r.intersection) },
            { label: `Only in ${genesetLabel(row)}`, value: String(onlyRow) },
            { label: `Only in ${genesetLabel(col)}`, value: String(onlyCol) },
            { label: 'Jaccard index', value: r.jaccard.toFixed(3) },
            { label: 'p-value', value: pText },
          ],
          note:
            p === null
              ? 'No null distribution covers these two set sizes, so there is no p-value.'
              : undefined,
        },
      });
    });
  });
  return { ids, sizes, cells, threshold: output.p_value_threshold ?? 1 };
}

/**
 * Whether a cell is greyed at a threshold: legacy greyed pairs whose p is above it. A pair
 * with no p-value cannot pass a test, so it is greyed too -- except at 1.0, which keeps
 * everything (it is legacy's "no filter" and its default). The diagonal is never greyed.
 */
export function vennCellGreyed(cell: VennGridCell, threshold: number): boolean {
  if (cell.diagonal || threshold >= 1) {
    return false;
  }
  return cell.p === null || cell.p > threshold;
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

export interface SunburstArc {
  /** Gene set label for a leaf; empty for a cluster. */
  name: string;
  /** Ring: 1 is the innermost drawn ring (the root itself is not drawn). */
  depth: number;
  /** Angles in radians. */
  start: number;
  end: number;
  leaf: boolean;
  /** For a cluster, 1 - its merge distance. */
  similarity: number | null;
  /** Gene sets under this arc. */
  members: string[];
}

/**
 * Legacy's "partitioned sunburst" of the clustering tree: each gene set an outer arc, each
 * cluster an inner arc spanning its members. Every gene set gets an equal angle: legacy
 * sized them by gene count, which the clustering output does not carry.
 */
export function sunburstArcs(tree: DendrogramNode | null | undefined): SunburstArc[] {
  if (!tree) {
    return [];
  }
  const leavesOf = (node: DendrogramNode): string[] =>
    node.children?.length ? node.children.flatMap(leavesOf) : [node.name];
  const total = leavesOf(tree).length;
  const arcs: SunburstArc[] = [];
  const walk = (node: DendrogramNode, depth: number, start: number) => {
    const members = leavesOf(node);
    const end = start + (2 * Math.PI * members.length) / total;
    const leaf = !node.children?.length;
    if (depth > 0) {
      arcs.push({
        name: leaf ? node.name : '',
        depth,
        start,
        end,
        leaf,
        similarity: leaf ? null : 1 - node.height,
        members,
      });
    }
    let at = start;
    for (const child of node.children ?? []) {
      walk(child, depth + 1, at);
      at += (2 * Math.PI * leavesOf(child).length) / total;
    }
  };
  walk(tree, 0, 0);
  return arcs;
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

export interface GeneNetwork {
  /** False when the result has no gene -> gene set map (a worker older than the field). */
  available: boolean;
  nodes: { id: string; cluster: number | null; genesets: string[] }[];
  edges: { source: string; target: string; genesets: string[] }[];
  /** Over the budget: too many links to draw legibly, so none are returned. */
  tooLarge: boolean;
  budget: number;
  clusters: number;
}

/**
 * Legacy DBSCAN's "wires" view: genes linked when they share an input gene set, coloured by
 * cluster, genes in no cluster as noise. A gene set of n genes links n(n-1)/2 pairs, so the
 * links grow fast; past `budget` the network is refused rather than drawn as a hairball, as
 * legacy refused (it drew nothing once one gene set passed 150 pairs).
 */
export function dbscanNetwork(
  output: { ran: boolean; clusters: string[][]; gene_genesets?: Record<string, string[]> | null },
  budget = 3000,
): GeneNetwork {
  const memberships = output.gene_genesets;
  const empty = { nodes: [], edges: [], tooLarge: false, budget, clusters: output.clusters.length };
  if (!memberships) {
    return { available: false, ...empty };
  }
  const clusterOf = new Map<string, number>();
  output.clusters.forEach((genes, index) => genes.forEach((gene) => clusterOf.set(gene, index)));
  const genes = [...new Set([...Object.keys(memberships), ...clusterOf.keys()])].sort();
  const bySet = new Map<string, string[]>();
  for (const gene of genes) {
    for (const set of memberships[gene] ?? []) {
      bySet.set(String(set), [...(bySet.get(String(set)) ?? []), gene]);
    }
  }
  const edges = new Map<string, { source: string; target: string; genesets: string[] }>();
  for (const [set, members] of bySet) {
    for (let a = 0; a < members.length; a++) {
      for (let b = a + 1; b < members.length; b++) {
        const key = `${members[a]}\u0000${members[b]}`;
        const edge = edges.get(key);
        if (edge) {
          edge.genesets.push(set);
        } else {
          if (edges.size >= budget) {
            return { available: true, ...empty, tooLarge: true };
          }
          edges.set(key, { source: members[a], target: members[b], genesets: [set] });
        }
      }
    }
  }
  return {
    available: true,
    nodes: genes.map((gene) => ({
      id: gene,
      cluster: clusterOf.get(gene) ?? null,
      genesets: (memberships[gene] ?? []).map(String),
    })),
    edges: [...edges.values()],
    tooLarge: false,
    budget,
    clusters: output.clusters.length,
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
  /**
   * For Except, genes in exactly one distinct gene set that the tool left out. The same
   * row counting drops them: two identifier rows in one set look like two sets (G3-830).
   */
  missingFromExcept: number;
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
    missingFromExcept:
      relation === 'except'
        ? [...genes.values()].filter((gene) => gene.sets.length === 1 && !resultKeys.has(gene.key))
            .length
        : 0,
    combinations: [...combos.entries()]
      .map(([signature, size]) => ({
        sets: signature ? signature.split(',').map(Number) : [],
        size,
      }))
      .sort((a, b) => b.size - a.size),
  };
}

/** Species by GeneWeaver species id; the same list as the species tag component. */
export const SPECIES_NAMES: Record<number, string> = {
  1: 'Mouse',
  2: 'Human',
  3: 'Rat',
  4: 'Zebrafish',
  5: 'Fruit fly',
  6: 'Macaque',
  7: 'Nematode',
  8: 'Yeast',
  9: 'Chicken',
  10: 'Western clawed frog',
  11: 'African clawed frog',
};

export interface SpeciesSummaryRow {
  species: number;
  name: string;
  /** Genes found only in this species' gene sets. */
  specific: number;
  /** Genes matched by homology to a gene in at least one other species. */
  shared: number;
  total: number;
}

/**
 * Legacy BooleanAlgebra's species table, for a request spanning species. Across species the
 * tool keys each gene by its homology group, so a key whose rows carry two species is a
 * gene matched across them. Counted over every input gene, as legacy's table was, not just
 * the relation's answer. Null for a single species: the table would say nothing.
 */
export function speciesSummary(output: BooleanAlgebraOutput): SpeciesSummaryRow[] | null {
  const speciesOfKey = Object.values(output.bool_results).map(
    (rows) => new Set(rows.map((row) => Number(row[2]))),
  );
  const all = [...new Set(speciesOfKey.flatMap((set) => [...set]))].sort((a, b) => a - b);
  if (all.length < 2) {
    return null;
  }
  return all.map((species) => {
    const keys = speciesOfKey.filter((set) => set.has(species));
    const shared = keys.filter((set) => set.size > 1).length;
    return {
      species,
      name: SPECIES_NAMES[species] ?? `Species ${species}`,
      specific: keys.length - shared,
      shared,
      total: keys.length,
    };
  });
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

export interface MsetEuler {
  universe: number;
  list1: number;
  list2: number;
  shared: number;
  /** Radii with the universe's as 1, and the two lists' centres on its horizontal axis. */
  r1: number;
  r2: number;
  /** Centre distance between the two lists, same units. */
  distance: number;
}

/**
 * Legacy MSET's "size comparison": the universe as a circle holding both lists, every area
 * proportional to its gene count and the lists' lens to the genes they share. Uses the
 * lists' sizes *in the universe* (what the test samples from). Legacy rescaled the
 * intersection by `min(list sizes) / 100` before solving the lens, which drew the wrong
 * overlap; this uses the shared count itself. Null when the summary lacks the counts.
 */
export function msetEuler(output: { mset_data: Record<string, string> }): MsetEuler | null {
  const read = (...keys: string[]) => {
    for (const key of keys) {
      const value = Number.parseInt(output.mset_data[key] ?? '', 10);
      if (Number.isFinite(value)) {
        return value;
      }
    }
    return NaN;
  };
  const universe = read('Universe Size');
  const list1 = read('List 1 / Universe', 'List 1 Size');
  const list2 = read('List 2 / Universe', 'List 2 Size');
  const shared = read('List 1/2 Intersect');
  if (![universe, list1, list2, shared].every(Number.isFinite) || universe <= 0) {
    return null;
  }
  // Area pi * r^2 per circle against the universe's pi * 1^2.
  const r1 = Math.sqrt(list1 / universe);
  const r2 = Math.sqrt(list2 / universe);
  const distance = distanceForOverlap(r1, r2, (Math.PI * shared) / universe);
  return { universe, list1, list2, shared, r1, r2, distance };
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

/**
 * Legacy's "highlight genes or gene sets": the displayed bicliques holding a match for the
 * query. A gene matches by symbol, ignoring case; a gene set by id, with or without "GS".
 * Several terms can be given, separated by commas or spaces; a biclique matches any of them.
 */
export function phenomeMapMatches(nodes: PhenomeMapNode[], query: string): Set<number> {
  const terms = query
    .split(/[\s,]+/)
    .map((term) => term.trim().toLowerCase())
    .filter(Boolean);
  const matched = new Set<number>();
  if (!terms.length) {
    return matched;
  }
  for (const node of nodes) {
    if (node.displayed === false) {
      continue;
    }
    const genes = new Set(node.genes.map((gene) => gene.toLowerCase()));
    const sets = new Set(node.genesets.map((id) => String(id).toLowerCase()));
    const hit = terms.some(
      (term) => genes.has(term) || sets.has(term.replace(/^gs/, '')),
    );
    if (hit) {
      matched.add(node.id);
    }
  }
  return matched;
}

/** Legacy's stats panel, from what the result carries. */
export function phenomeMapStats(output: {
  nodes: PhenomeMapNode[];
  num_genes?: number;
  num_genesets?: number;
}): TooltipRow[] {
  const shown = output.nodes.filter((node) => node.displayed !== false);
  const rows: TooltipRow[] = [];
  if (output.num_genesets !== undefined) {
    rows.push({ label: 'Gene sets', value: String(output.num_genesets) });
  }
  if (output.num_genes !== undefined) {
    rows.push({ label: 'Genes', value: String(output.num_genes) });
  }
  rows.push({ label: 'Bicliques shown', value: String(shown.length) });
  if (shown.length !== output.nodes.length) {
    rows.push({ label: 'Bicliques hidden', value: String(output.nodes.length - shown.length) });
  }
  const ids = new Set(shown.map((node) => node.id));
  const links = shown.reduce(
    (sum, node) => sum + (node.children ?? []).filter((link) => ids.has(link.target)).length,
    0,
  );
  rows.push({ label: 'Links', value: String(links) });
  if (shown.length) {
    rows.push({ label: 'Levels', value: String(Math.max(...shown.map((node) => node.depth)) + 1) });
    rows.push({ label: 'Largest biclique', value: `${Math.max(...shown.map((n) => n.genes.length))} genes` });
  }
  return rows;
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
