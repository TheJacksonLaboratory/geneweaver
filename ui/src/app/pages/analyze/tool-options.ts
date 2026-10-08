/**
 * The options each analysis tool offers on /next/analyze.
 *
 * Mirrors legacy's `odestatic.tool_param` by hand: the labels, choices and defaults are the
 * ones legacy shows (read from dev's table), and `key` is the parameter name the v3 API takes
 * for that tool. Legacy options the v3 tools cannot honour are left out rather than shown
 * doing nothing -- PhenomeMap's MaxInNode, Permutations and PermutationTimeLimit.
 */

export type OptionValue = boolean | number | string;
export type OptionValues = Record<string, OptionValue>;

export interface OptionChoice {
  label: string;
  value: OptionValue;
}

interface BaseOption {
  /** The API parameter name. */
  key: string;
  label: string;
  help?: string;
  /** Shown -- and sent -- only when this holds for the current values. */
  visibleWhen?: (values: OptionValues) => boolean;
}

export interface ChoiceOption extends BaseOption {
  kind: 'select' | 'radio';
  choices: OptionChoice[];
  default: OptionValue;
}

export interface NumberOption extends BaseOption {
  kind: 'number';
  min: number;
  default: number;
}

export interface CheckboxOption extends BaseOption {
  kind: 'checkbox';
  default: boolean;
}

export type ToolOptionDefinition = ChoiceOption | NumberOption | CheckboxOption;

/** Legacy's "Homology: Included / Excluded", Included by default for every tool. */
const HOMOLOGY: ChoiceOption = {
  key: 'include_homology',
  label: 'Homology',
  kind: 'radio',
  choices: [
    { label: 'Included', value: true },
    { label: 'Excluded', value: false },
  ],
  default: true,
  help:
    'Included treats orthologous genes from different species as the same gene, so gene ' +
    'sets from different species can overlap.',
};

const PAIRWISE_DELETION: CheckboxOption = {
  key: 'pairwise_deletion',
  label: 'Pairwise deletion',
  kind: 'checkbox',
  default: false,
  help:
    'For two gene sets measured on different microarray platforms, count only the genes ' +
    'both platforms measure. No effect on gene sets of gene identifiers.',
};

/** Legacy's p-value choices; it shows them as written, so the labels keep "0.10". */
const P_VALUE_CHOICES: OptionChoice[] = [
  { label: '1.0', value: 1.0 },
  { label: '0.5', value: 0.5 },
  { label: '0.10', value: 0.1 },
  { label: '0.05', value: 0.05 },
  { label: '0.01', value: 0.01 },
];

export const TOOL_OPTIONS: Record<string, ToolOptionDefinition[]> = {
  upset: [
    HOMOLOGY,
    {
      key: 'include_zeros',
      label: 'Include empty combinations',
      kind: 'checkbox',
      default: false,
      help: 'Also list the combinations no gene belongs to (legacy: zero-size intersections).',
    },
  ],
  jaccard_similarity: [
    HOMOLOGY,
    PAIRWISE_DELETION,
    {
      key: 'p_value_threshold',
      label: 'p-value threshold',
      kind: 'select',
      choices: P_VALUE_CHOICES,
      default: 1.0,
      help:
        'Pairs with a p-value above this are shown as not significant. It only shades and ' +
        'flags results; no pair is removed.',
    },
  ],
  jaccard_clustering: [
    HOMOLOGY,
    {
      key: 'method',
      label: 'Method',
      kind: 'select',
      choices: [
        { label: 'Ward', value: 'ward' },
        { label: 'Single', value: 'single' },
        { label: 'Centroid', value: 'centroid' },
        { label: 'McQuitty', value: 'mcquitty' },
        { label: 'Average', value: 'average' },
        { label: 'Complete', value: 'complete' },
      ],
      default: 'ward',
      help: 'How the distance between two clusters is measured when deciding which to merge.',
    },
  ],
  hypergeometric: [HOMOLOGY, PAIRWISE_DELETION],
  combine: [HOMOLOGY],
  boolean_algebra: [
    {
      key: 'relation',
      label: 'Relation',
      kind: 'radio',
      choices: [
        { label: 'Union', value: 'union' },
        { label: 'Intersection', value: 'intersection' },
        { label: 'Symmetric difference', value: 'except' },
      ],
      default: 'union',
    },
    {
      key: 'at_least',
      label: 'In at least N gene sets',
      kind: 'number',
      min: 1,
      default: 2,
      help: 'Report the genes found in at least this many of the gene sets.',
      visibleWhen: (values) => values['relation'] === 'intersection',
    },
  ],
  dbscan: [
    HOMOLOGY,
    {
      key: 'epsilon',
      label: 'Epsilon',
      kind: 'number',
      min: 1,
      default: 1,
      help: 'How many gene-set links apart two genes may be and still count as neighbours.',
    },
    {
      key: 'min_points',
      label: 'Minimum points',
      kind: 'number',
      min: 1,
      default: 1,
      help: 'How many neighbours a gene needs to start a cluster.',
    },
  ],
  mset: [
    {
      key: 'number_of_samples',
      label: 'Number of trials',
      kind: 'select',
      choices: [5000, 10000, 15000, 30000].map((value) => ({ label: String(value), value })),
      default: 5000,
      help: 'Random samples drawn to estimate the p-value. More trials take longer.',
    },
  ],
  phenome_map: [
    HOMOLOGY,
    {
      key: 'disable_bootstrap',
      label: 'Disable bootstrap',
      kind: 'checkbox',
      default: false,
      help: 'Skip the bootstrap reduction that otherwise runs on graphs of over 100 nodes.',
    },
    {
      key: 'use_fdr',
      label: 'Use FDR',
      kind: 'checkbox',
      default: false,
      help: 'Derive the link threshold with a Benjamini-Hochberg false discovery rate correction.',
    },
    {
      key: 'p_value_threshold',
      label: 'p-value threshold',
      kind: 'select',
      choices: P_VALUE_CHOICES,
      default: 1.0,
      help: 'Keep only the links scoring at or below this; 1.0 keeps them all.',
    },
    {
      key: 'min_genes',
      label: 'Minimum genes',
      kind: 'select',
      choices: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25].map((value) => ({
        label: String(value),
        value,
      })),
      default: 1,
      help: 'The fewest genes a node may hold.',
    },
    {
      key: 'max_level',
      label: 'Maximum level',
      kind: 'select',
      choices: [0, 10, 20, 40, 60, 80, 100].map((value) => ({ label: String(value), value })),
      default: 40,
      help: 'Cut the graph below the first level wider than this; 0 keeps every level.',
    },
  ],
};

/** The selected tool's options at their legacy defaults. */
export function defaultOptionValues(tool: string): OptionValues {
  return Object.fromEntries((TOOL_OPTIONS[tool] ?? []).map((option) => [option.key, option.default]));
}

/** The options to show -- and send -- for these values. */
export function visibleOptions(tool: string, values: OptionValues): ToolOptionDefinition[] {
  return (TOOL_OPTIONS[tool] ?? []).filter((option) => !option.visibleWhen || option.visibleWhen(values));
}

/** Why the values cannot be sent, or `undefined` if they can. */
export function optionProblem(tool: string, values: OptionValues): string | undefined {
  for (const option of visibleOptions(tool, values)) {
    if (option.kind !== 'number') {
      continue;
    }
    const value = values[option.key];
    if (typeof value !== 'number' || !Number.isInteger(value) || value < option.min) {
      return `${option.label} must be a whole number of at least ${option.min}.`;
    }
  }
  return undefined;
}
