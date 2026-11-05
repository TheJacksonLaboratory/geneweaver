/**
 * The run's gene set threshold choice on /next/analyze.
 *
 * Curation decided (Tessa, Heidi; 2026-10-16) that a gene set is not inherently thresholded:
 * it is its full list of genes and scores, and whoever runs an analysis may threshold it for
 * that run. So every tool takes one of:
 *
 * - every gene (the default);
 * - each gene set's own stored threshold, the uploader's -- one click;
 * - the run's own cutoffs, one per score type: a p- or q-value at most its cutoff, a
 *   correlation or effect inside its range. Binary gene sets have no score to cut.
 *
 * The API's side is `ThresholdOptions` (`geneweaver.tools.thresholds`).
 */

export type ThresholdMode = 'none' | 'uploader' | 'custom';

export interface RunThresholds {
  mode: ThresholdMode;
  pValue: number | null;
  qValue: number | null;
  correlationLow: number | null;
  correlationHigh: number | null;
  effectLow: number | null;
  effectHigh: number | null;
}

/** What a result says it ran with: the API's echo of the choice. */
export interface ThresholdChoice {
  threshold?: ThresholdMode;
  p_value?: number | null;
  q_value?: number | null;
  correlation_low?: number | null;
  correlation_high?: number | null;
  effect_low?: number | null;
  effect_high?: number | null;
}

export const THRESHOLD_MODES: { value: ThresholdMode; label: string; help: string }[] = [
  {
    value: 'none',
    label: 'All genes',
    help: 'Every gene in each gene set, with no threshold.',
  },
  {
    value: 'uploader',
    label: "Uploader's thresholds",
    help: "Each gene set's own stored threshold: p- and q-values at most it, correlation and effect inside its range.",
  },
  {
    value: 'custom',
    label: 'My thresholds',
    help: 'Your cutoffs, per score type, for this run only. A score type you leave empty keeps all its genes.',
  },
];

export function defaultRunThresholds(): RunThresholds {
  return {
    mode: 'none',
    pValue: null,
    qValue: null,
    correlationLow: null,
    correlationHigh: null,
    effectLow: null,
    effectHigh: null,
  };
}

const CUTOFFS: [keyof RunThresholds, keyof ThresholdChoice][] = [
  ['pValue', 'p_value'],
  ['qValue', 'q_value'],
  ['correlationLow', 'correlation_low'],
  ['correlationHigh', 'correlation_high'],
  ['effectLow', 'effect_low'],
  ['effectHigh', 'effect_high'],
];

/** The request parameters, as `ThresholdOptions` in the API takes them. */
export interface ThresholdParams {
  threshold: ThresholdMode;
  p_value?: number;
  q_value?: number;
  correlation_low?: number;
  correlation_high?: number;
  effect_low?: number;
  effect_high?: number;
}

/** The request parameters: the mode, and the cutoffs given when it is custom. */
export function thresholdParams(thresholds: RunThresholds): ThresholdParams {
  const params: ThresholdParams = { threshold: thresholds.mode };
  if (thresholds.mode === 'custom') {
    for (const [key, name] of CUTOFFS) {
      const value = thresholds[key];
      if (typeof value === 'number' && Number.isFinite(value) && name !== 'threshold') {
        params[name] = value;
      }
    }
  }
  return params;
}

/** Why this choice cannot be sent, or `undefined`. */
export function thresholdProblem(thresholds: RunThresholds): string | undefined {
  if (thresholds.mode !== 'custom') {
    return undefined;
  }
  const given = CUTOFFS.filter(([key]) => typeof thresholds[key] === 'number');
  if (!given.length) {
    return 'Enter at least one cutoff, or choose All genes.';
  }
  for (const [name, low, high] of [
    ['correlation', thresholds.correlationLow, thresholds.correlationHigh],
    ['effect', thresholds.effectLow, thresholds.effectHigh],
  ] as const) {
    if (low !== null && high !== null && low > high) {
      return `The ${name} range's low end is above its high end.`;
    }
  }
  for (const [name, value] of [
    ['p-value', thresholds.pValue],
    ['q-value', thresholds.qValue],
  ] as const) {
    if (value !== null && (value < 0 || value > 1)) {
      return `A ${name} cutoff must be between 0 and 1.`;
    }
  }
  return undefined;
}

const given = (value: number | null | undefined): value is number => typeof value === 'number';

const range = (low: number | null | undefined, high: number | null | undefined) =>
  given(low) && given(high) ? `${low} to ${high}` : given(low) ? `at least ${low}` : `at most ${high}`;

/** One line saying which genes a result counted, from the API's echo of the choice. */
export function describeThresholds(choice: ThresholdChoice | null | undefined): string {
  switch (choice?.threshold ?? 'none') {
    case 'uploader':
      return "Genes: each gene set's uploader threshold.";
    case 'custom': {
      const parts: string[] = [];
      if (given(choice?.p_value)) parts.push(`p-value ≤ ${choice?.p_value}`);
      if (given(choice?.q_value)) parts.push(`q-value ≤ ${choice?.q_value}`);
      if (given(choice?.correlation_low) || given(choice?.correlation_high)) {
        parts.push(`correlation ${range(choice?.correlation_low, choice?.correlation_high)}`);
      }
      if (given(choice?.effect_low) || given(choice?.effect_high)) {
        parts.push(`effect ${range(choice?.effect_low, choice?.effect_high)}`);
      }
      return `Genes: custom thresholds -- ${parts.join('; ')}. Other score types: all genes.`;
    }
    default:
      return 'Genes: all genes in each gene set (no threshold).';
  }
}
