import {
  defaultRunThresholds,
  describeThresholds,
  RunThresholds,
  thresholdParams,
  thresholdProblem,
} from './run-thresholds';

const custom = (changes: Partial<RunThresholds>): RunThresholds => ({
  ...defaultRunThresholds(),
  mode: 'custom',
  ...changes,
});

describe('run thresholds', () => {
  it('runs on every gene by default: a gene set is not inherently thresholded', () => {
    expect(defaultRunThresholds().mode).toBe('none');
    expect(thresholdParams(defaultRunThresholds())).toEqual({ threshold: 'none' });
  });

  it("sends the uploader's thresholds as one choice, with no cutoffs", () => {
    const thresholds = { ...defaultRunThresholds(), mode: 'uploader' as const, pValue: 0.01 };
    expect(thresholdParams(thresholds)).toEqual({ threshold: 'uploader' });
    expect(thresholdProblem(thresholds)).toBeUndefined();
  });

  it('sends only the custom cutoffs given', () => {
    expect(thresholdParams(custom({ qValue: 0.05, effectLow: -2 }))).toEqual({
      threshold: 'custom',
      q_value: 0.05,
      effect_low: -2,
    });
  });

  it.each([
    [custom({}), 'at least one cutoff'],
    [custom({ correlationLow: 0.8, correlationHigh: 0.2 }), 'correlation'],
    [custom({ pValue: 2 }), 'between 0 and 1'],
  ])('says what is wrong with %o', (thresholds, message) => {
    expect(thresholdProblem(thresholds)).toContain(message);
  });

  it.each([
    [undefined, 'all genes in each gene set'],
    [{ threshold: 'uploader' as const }, "each gene set's uploader threshold"],
    [
      { threshold: 'custom' as const, p_value: 0.01, q_value: null, correlation_low: -0.5, correlation_high: 0.5 },
      'p-value ≤ 0.01; correlation -0.5 to 0.5',
    ],
    [{ threshold: 'custom' as const, effect_high: 3 }, 'effect at most 3'],
  ])('describes %o for a result', (choice, text) => {
    expect(describeThresholds(choice)).toContain(text);
  });
});
