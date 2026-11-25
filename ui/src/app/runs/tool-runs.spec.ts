import {
  describeRunError,
  downloadUrl,
  geneCountsFromIntersections,
  runDownloads,
  toolLabel,
} from './tool-runs';
import { environment } from '../../environments/environment';

describe('runDownloads', () => {
  const formats = (tool: string | null) =>
    runDownloads(tool).map((d) => [d.format, d.table ?? null]);

  it('offers CSV and TSV of the one table, then JSON', () => {
    expect(formats('upset')).toEqual([
      ['csv', 'intersections'],
      ['tsv', 'intersections'],
      ['json', null],
    ]);
  });

  it('names each table where a tool has several', () => {
    const labels = runDownloads('abba').map((d) => d.label);
    expect(labels).toEqual([
      'CSV (gene sets)',
      'TSV (gene sets)',
      'CSV (genes)',
      'TSV (genes)',
      'JSON (full result)',
    ]);
  });

  it("offers Combine's legacy matrix and the clustering tree", () => {
    expect(formats('combine')).toContainEqual(['odemat', null]);
    expect(formats('jaccard_clustering')).toEqual([
      ['newick', null],
      ['json', null],
    ]);
  });

  it('falls back to JSON for a run whose tool is unknown', () => {
    expect(formats(null)).toEqual([['json', null]]);
    expect(formats('something_new')).toEqual([['json', null]]);
  });
});

describe('downloadUrl', () => {
  it("is the API's download route, with the table when there is one", () => {
    const base = environment.urls.geneWeaverApi;
    expect(downloadUrl(7, { label: '', format: 'csv', table: 'genes' })).toBe(
      `${base}/tools/runs/7/download?format=csv&table=genes`,
    );
    expect(downloadUrl(7, { label: '', format: 'json' })).toBe(
      `${base}/tools/runs/7/download?format=json`,
    );
  });
});

describe('describeRunError', () => {
  it("uses the API's own detail where it gives one", () => {
    expect(describeRunError({ status: 409, error: { detail: 'Run it again.' } }, 'open it')).toBe(
      'Run it again.',
    );
  });

  it('explains each run status without a detail', () => {
    expect(describeRunError({ status: 401 }, 'see your analyses')).toBe(
      'Sign in to see your analyses.',
    );
    expect(describeRunError({ status: 404 }, 'x')).toContain('not one of yours');
    expect(describeRunError({ status: 409 }, 'x')).toContain('run the analysis again');
    expect(describeRunError({ status: 403 }, 'x')).toContain('can no longer read');
    expect(describeRunError({ status: 500 }, 'delete it')).toBe('Could not delete it (HTTP 500).');
  });
});

describe('geneCountsFromIntersections', () => {
  it('sums the exclusive intersections each gene set is in', () => {
    const intersections = [
      { geneset_ids: ['1', '2'], size: 2 },
      { geneset_ids: ['1'], size: 3 },
    ];
    expect(geneCountsFromIntersections([1, 2, 3], intersections)).toEqual({
      '1': 5,
      '2': 2,
      '3': 0,
    });
  });
});

describe('toolLabel', () => {
  it("uses legacy's names, and the key for a tool it does not know", () => {
    expect(toolLabel('phenome_map')).toBe('HiSim Graph');
    expect(toolLabel('new_tool')).toBe('new_tool');
    expect(toolLabel(null)).toBe('Unknown tool');
  });
});
