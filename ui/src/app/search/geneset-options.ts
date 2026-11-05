/**
 * The pure half of the gene set search fields (the analyze page's picker and the /next search
 * field): parsing typed ids and describing a search result. No Angular, so it is tested
 * without a DOM.
 */
import { GeneSet } from '../models/gene-set';
import { scoreTypeName, speciesName, TIER_OPTIONS } from './search-filters';

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
    geneset.species_id !== undefined ? speciesName(geneset.species_id) : '',
    geneset.curation_id !== undefined
      ? (TIER_OPTIONS.find((tier) => tier.id === geneset.curation_id)?.label ?? 'No tier')
      : '',
    geneset.score_type !== undefined ? scoreTypeName(geneset.score_type) : '',
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
