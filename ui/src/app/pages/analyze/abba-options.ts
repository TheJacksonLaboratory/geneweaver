/**
 * ABBA's search form: legacy's `ABBA_options.html`, with its labels, choices and defaults.
 *
 * Not part of `tool-options.ts`: ABBA is seeded with genes rather than gene sets, and its
 * options (a set of tiers, an optional species restriction, "Auto" thresholds) do not fit
 * that table's one-value-per-option shape.
 */

/** Request bounds, mirroring `ABBARequest` in `api/schemas/tools.py`. */
export const ABBA_MAX_GENES = 1000;
export const ABBA_MAX_GENESETS = 20;

export interface AbbaOptions {
  /** Legacy offered "Ignore homology", unchecked; this is its inverse. */
  includeHomology: boolean;
  /** `null` is "Auto". */
  minGenes: number | null;
  minGenesets: number | null;
  tiers: number[];
  restrictSpecies: boolean;
  speciesIds: number[];
}

export function defaultAbbaOptions(): AbbaOptions {
  return {
    includeHomology: true,
    minGenes: null,
    minGenesets: null,
    tiers: [1, 2, 3],
    restrictSpecies: false,
    speciesIds: [],
  };
}

/** Legacy's tier checkboxes, 1-3 checked. */
export const ABBA_TIERS: { id: number; label: string }[] = [
  { id: 1, label: 'Public resources (Tier I)' },
  { id: 2, label: 'Auto-curated (Tier II)' },
  { id: 3, label: 'Curated (Tier III)' },
  { id: 4, label: 'Provisional (Tier IV)' },
  { id: 5, label: 'Private (Tier V)' },
];

/** Legacy's species checkboxes, as it listed them. */
export const ABBA_SPECIES: { id: number; label: string }[] = [
  { id: 1, label: 'Mus musculus' },
  { id: 2, label: 'Homo sapiens' },
  { id: 3, label: 'Rattus norvegicus' },
  { id: 4, label: 'Danio rerio' },
  { id: 5, label: 'Drosophila melanogaster' },
  { id: 6, label: 'Macaca mulatta' },
  { id: 8, label: 'Caenorhabditis elegans' },
  { id: 9, label: 'Saccharomyces cerevisiae' },
  { id: 10, label: 'Gallus gallus' },
];

/** "Minimum gene sets": Auto, then 1 to 50, as legacy offered. */
export const MIN_GENESETS_CHOICES: (number | null)[] = [
  null,
  ...Array.from({ length: 50 }, (_, index) => index + 1),
];

/**
 * "Minimum genes": Auto, then 1 up to the number of seed genes typed, as legacy grew the
 * list with each gene added. Seeded by gene sets alone, legacy offered only Auto; here up to
 * 50, since their members count as seeds too.
 */
export function minGenesChoices(seedGeneCount: number): (number | null)[] {
  const top = seedGeneCount > 0 ? Math.min(seedGeneCount, 50) : 50;
  return [null, ...Array.from({ length: top }, (_, index) => index + 1)];
}

/** Toggle `id` in a list, keeping it sorted. */
export function toggled(list: number[], id: number): number[] {
  return list.includes(id) ? list.filter((value) => value !== id) : [...list, id].sort((a, b) => a - b);
}

/**
 * Why this search cannot be sent, or `undefined` if it can. The empty search is reported as
 * `undefined` too -- the user has not started -- and kept from running by `abbaCanRun`.
 */
export function abbaProblem(
  genes: string[],
  genesetIds: number[],
  options: AbbaOptions,
): string | undefined {
  if (genes.length > ABBA_MAX_GENES) {
    return `Enter at most ${ABBA_MAX_GENES} seed genes; ${genes.length} entered.`;
  }
  if (genesetIds.length > ABBA_MAX_GENESETS) {
    return `Select at most ${ABBA_MAX_GENESETS} gene sets; ${genesetIds.length} entered.`;
  }
  if (!options.tiers.length) {
    return 'Choose at least one curation tier.';
  }
  if (options.restrictSpecies && !options.speciesIds.length) {
    return 'Choose at least one species to restrict to, or search all species.';
  }
  return undefined;
}

export function abbaCanRun(genes: string[], genesetIds: number[], options: AbbaOptions): boolean {
  return (genes.length > 0 || genesetIds.length > 0) && !abbaProblem(genes, genesetIds, options);
}

/** The `POST /tools/abba` body. */
export function abbaRequestBody(genes: string[], genesetIds: number[], options: AbbaOptions) {
  return {
    genes,
    geneset_ids: genesetIds,
    include_homology: options.includeHomology,
    min_genes: options.minGenes,
    min_genesets: options.minGenesets,
    tiers: [...options.tiers].sort((a, b) => a - b),
    species_ids: options.restrictSpecies ? [...options.speciesIds].sort((a, b) => a - b) : null,
  };
}
