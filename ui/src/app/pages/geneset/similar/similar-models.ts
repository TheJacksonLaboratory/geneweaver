/**
 * Similar gene sets on /next/geneset/:id: legacy's "Find Similar GeneSets" page
 * (`/viewSimilarGenesets/<gs_id>/<grp_by>`, `similargenesets.html`).
 *
 * The API returns the top 500 gene sets by Jaccard (`POST /tools/similar_genesets`); these
 * shape them for legacy's three views: the list, grouped as legacy's grp_by grouped it; the
 * radar of average Jaccard per curation tier and species; and the bar chart of Jaccard by
 * rank.
 */

import { ThresholdChoice } from '../../analyze/run-thresholds';

export interface SimilarGeneset {
  gs_id: number;
  name: string;
  abbreviation: string | null;
  species_id: number;
  /** Null for a gene set never given a curation tier (`cur_id` is nullable). */
  tier: number | null;
  attribution: string | null;
  genes: number;
  shared: number;
  jaccard: number;
}

export interface SimilarGenesetsOutput {
  geneset_id: number;
  genes: number;
  thresholds: ThresholdChoice;
  compared: number;
  genesets: SimilarGeneset[];
  /** JSON object keys are strings. */
  species: Record<string, string>;
  tiers: Record<string, string>;
}

/** Legacy's grp_by: 0 none, 1 tier, 2 species, 3 attribution. */
export type GroupBy = 'none' | 'tier' | 'species' | 'attribution';

export const GROUP_BY_CHOICES: { value: GroupBy; label: string }[] = [
  { value: 'none', label: 'Most similar first' },
  { value: 'tier', label: 'Curation tier' },
  { value: 'species', label: 'Species' },
  { value: 'attribution', label: 'Attribution' },
];

export interface SimilarGroup {
  label: string;
  genesets: SimilarGeneset[];
}

export function tierLabel(output: SimilarGenesetsOutput, tier: number | null): string {
  return tier === null ? 'No tier' : (output.tiers[String(tier)] ?? `Tier ${tier}`);
}

export function speciesLabel(output: SimilarGenesetsOutput, species: number): string {
  return output.species[String(species)] ?? `Species ${species}`;
}

/**
 * The list in groups, each most similar first. Legacy ordered by the group column, then
 * Jaccard; groups here are in that same order (tier and species by id, attribution by
 * name, none last).
 */
export function groupSimilar(output: SimilarGenesetsOutput, by: GroupBy): SimilarGroup[] {
  if (by === 'none') {
    return [{ label: '', genesets: output.genesets }];
  }
  const keyOf = (gs: SimilarGeneset): string | number | null =>
    by === 'tier' ? gs.tier : by === 'species' ? gs.species_id : gs.attribution;
  const groups = new Map<string | number | null, SimilarGeneset[]>();
  for (const gs of output.genesets) {
    const key = keyOf(gs);
    groups.set(key, [...(groups.get(key) ?? []), gs]);
  }
  const keys = [...groups.keys()].sort((a, b) =>
    a === null ? 1 : b === null ? -1 : typeof a === 'number' ? a - (b as number) : String(a).localeCompare(String(b)),
  );
  return keys.map((key) => ({
    label:
      by === 'tier'
        ? tierLabel(output, key as number | null)
        : key === null
          ? 'No attribution'
          : by === 'species'
            ? speciesLabel(output, key as number)
            : String(key),
    genesets: groups.get(key) ?? [],
  }));
}

export interface RadarSeries {
  tier: number;
  label: string;
  /** Average Jaccard per axis, 0 where no gene set of the tier is of that species. */
  values: number[];
  count: number;
}

export interface RadarModel {
  axes: string[];
  series: RadarSeries[];
  max: number;
}

/**
 * Legacy's radar: for each curation tier, the average Jaccard of the listed gene sets of
 * each species. Legacy drew every species; this draws the species in the list, so the axes
 * carry data. Tiers with no gene set listed are left out, and so are gene sets with no
 * tier, as legacy's loop over tiers 1-5 left them out; they stay in the list.
 */
export function radarModel(output: SimilarGenesetsOutput): RadarModel {
  const speciesIds = [...new Set(output.genesets.map((gs) => gs.species_id))].sort((a, b) => a - b);
  const tiers = [
    ...new Set(output.genesets.map((gs) => gs.tier).filter((tier): tier is number => tier !== null)),
  ].sort((a, b) => a - b);
  const series = tiers.map((tier) => {
    const ofTier = output.genesets.filter((gs) => gs.tier === tier);
    return {
      tier,
      label: tierLabel(output, tier),
      count: ofTier.length,
      values: speciesIds.map((species) => {
        const cell = ofTier.filter((gs) => gs.species_id === species);
        return cell.length ? cell.reduce((sum, gs) => sum + gs.jaccard, 0) / cell.length : 0;
      }),
    };
  });
  return {
    axes: speciesIds.map((species) => speciesLabel(output, species)),
    series,
    max: Math.max(0, ...series.flatMap((s) => s.values)),
  };
}

/** Points of a radar polygon, for an SVG `points` attribute, centred on (0, 0). */
export function radarPoints(values: number[], max: number, radius: number): string {
  const n = values.length;
  return values
    .map((value, i) => {
      const angle = (2 * Math.PI * i) / n - Math.PI / 2;
      const r = max > 0 ? (value / max) * radius : 0;
      return `${(r * Math.cos(angle)).toFixed(1)},${(r * Math.sin(angle)).toFixed(1)}`;
    })
    .join(' ');
}

/** Where axis `i` of `n` ends, at `radius`. */
export function radarAxis(i: number, n: number, radius: number): { x: number; y: number } {
  const angle = (2 * Math.PI * i) / n - Math.PI / 2;
  return { x: radius * Math.cos(angle), y: radius * Math.sin(angle) };
}

/** Legacy's export (`/exportJacGeneList`): id, name, label, genes, Jaccard -- plus tier, species. */
export function similarCsv(output: SimilarGenesetsOutput): string {
  const quote = (value: string | number | null) => {
    const text = value === null ? '' : String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const header = ['gs_id', 'name', 'abbreviation', 'genes', 'shared', 'jaccard', 'tier', 'species'];
  const rows = output.genesets.map((gs) =>
    [
      `GS${gs.gs_id}`,
      gs.name,
      gs.abbreviation,
      gs.genes,
      gs.shared,
      gs.jaccard.toFixed(4),
      tierLabel(output, gs.tier),
      speciesLabel(output, gs.species_id),
    ]
      .map(quote)
      .join(','),
  );
  return [header.join(','), ...rows].join('\n') + '\n';
}
