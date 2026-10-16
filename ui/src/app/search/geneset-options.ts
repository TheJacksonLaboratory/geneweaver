/**
 * The pure half of the gene set picker on /next/analyze: parsing typed ids and describing a
 * search result. No Angular, so it is tested without a DOM.
 */
import { GeneSet } from '../../models/gene-set';
import { ABBA_SPECIES } from './abba-options';
import { tierLabel } from './visualizations/abba-models';

/** One search result, or one id typed in, as the picker shows it. */
export interface GenesetOption {
  id: number;
  /** The chip's text: `GS167180`, plus the abbreviation once it is known. */
  chip: string;
  abbreviation?: string;
  /** Species, tier, score type and size, for the suggestion's second line. */
  detail?: string;
}

/** Results per request; scrolling to the end of a page fetches the next. */
export const PAGE_SIZE = 25;

/** `odestatic.genesets.gs_threshold_type`, as `ScoreTypeInt` in `geneweaver.core.enum`. */
const SCORE_TYPES: Record<number, string> = {
  1: 'p-value',
  2: 'q-value',
  3: 'binary',
  4: 'correlation',
  5: 'effect',
};

const SPECIES = Object.fromEntries(ABBA_SPECIES.map((species) => [species.id, species.label]));

/** `167180` or `GS167180` (any case): a gene set id. */
const ID_TOKEN = /^(?:gs)?(\d+)$/i;

/**
 * The ids in typed or pasted text -- `514, 515`, `GS514 GS515` -- or `undefined` when any
 * token is not an id, because then the text is a search, not a list of ids.
 */
export function parseIds(text: string): number[] | undefined {
  const tokens = text.split(/[\s,;]+/).filter(Boolean);
  if (!tokens.length) {
    return undefined;
  }
  const ids: number[] = [];
  for (const token of tokens) {
    const match = ID_TOKEN.exec(token);
    const id = match ? Number(match[1]) : NaN;
    if (!Number.isInteger(id) || id <= 0) {
      return undefined;
    }
    ids.push(id);
  }
  return ids;
}

/** A search result as a suggestion. */
export function toOption(geneset: Pick<GeneSet, 'id'> & Partial<GeneSet>): GenesetOption {
  const parts = [
    geneset.species_id !== undefined ? (SPECIES[geneset.species_id] ?? `species ${geneset.species_id}`) : '',
    geneset.curation_id !== undefined ? tierLabel(geneset.curation_id) : '',
    geneset.score_type !== undefined ? (SCORE_TYPES[geneset.score_type] ?? '') : '',
    geneset.count !== undefined && geneset.count !== null ? `${geneset.count.toLocaleString()} genes` : '',
  ].filter(Boolean);
  const abbreviation = geneset.abbreviation || geneset.name || undefined;
  return {
    id: geneset.id,
    chip: abbreviation ? `GS${geneset.id} · ${abbreviation}` : `GS${geneset.id}`,
    abbreviation,
    detail: parts.join(' · ') || undefined,
  };
}

/** `existing`, then the options in `page` not already in it: later pages can repeat a row. */
export function appendPage(existing: GenesetOption[], page: GenesetOption[]): GenesetOption[] {
  const seen = new Set(existing.map((option) => option.id));
  return [...existing, ...page.filter((option) => !seen.has(option.id) && seen.add(option.id))];
}
