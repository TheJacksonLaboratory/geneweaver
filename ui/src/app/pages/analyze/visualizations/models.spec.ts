import { FIXTURES } from './fixtures';
import {
  booleanModel,
  BooleanAlgebraOutput,
  combineModel,
  dbscanModel,
  dendrogramModel,
  distanceForOverlap,
  formatEmpiricalP,
  formatP,
  hypergeometricMatrix,
  jaccardMatrix,
  lensArea,
  msetModel,
  phenomeMapElements,
  phenomeMapPositions,
  upsetModel,
  vennLayout,
} from './models';

describe('formatP', () => {
  it('never shows a bare 0 or a blank', () => {
    expect(formatP(0)).toBe('< 1e-300');
    expect(formatP(null)).toBe('no p-value');
    expect(formatP(0.002)).toBe('0.002');
    expect(formatP(9.69e-26)).toBe('9.7e-26');
  });
});

describe('formatEmpiricalP', () => {
  it('bounds a sampled p of 0 by the sample count, never "< 1e-300"', () => {
    expect(formatEmpiricalP(0, 1000)).toBe('< 0.001 (no sample as extreme)');
    expect(formatEmpiricalP(0)).toBe('≈ 0 (no sampled pair as similar)');
    expect(formatEmpiricalP(0.002)).toBe('0.002');
  });
});

describe('upsetModel', () => {
  const { geneset_ids, gene_counts, intersections } = FIXTURES.upset;

  it('draws the largest combinations first, and never empty ones', () => {
    const model = upsetModel(geneset_ids, gene_counts, intersections);
    const sizes = model.bars.map((bar) => bar.size);
    expect(sizes).toEqual([...sizes].sort((a, b) => b - a));
    expect(sizes.every((size) => size > 0)).toBe(true);
    expect(model.sets.map((set) => set.size)).toEqual(
      geneset_ids.map((id: number) => gene_counts[String(id) as keyof typeof gene_counts]),
    );
  });

  it('knows every set\'s unique genes and the total, for the tooltips', () => {
    const model = upsetModel(geneset_ids, gene_counts, intersections);
    expect(model.total).toBe(
      intersections.reduce((sum: number, i: { size: number }) => sum + i.size, 0),
    );
    for (const set of model.sets) {
      const only = intersections.find(
        (i: { geneset_ids: string[] }) => i.geneset_ids.length === 1 && i.geneset_ids[0] === set.id,
      );
      expect(set.unique).toBe(only?.size ?? 0);
    }
  });

  it('caps the bars and says how many it left out', () => {
    const model = upsetModel(geneset_ids, gene_counts, intersections, 5);
    expect(model.bars).toHaveLength(5);
    expect(model.hidden).toBe(intersections.filter((i: { size: number }) => i.size > 0).length - 5);
  });
});

describe('pairwise matrices', () => {
  it('JaccardSimilarity: a symmetric matrix with a blank diagonal and p in the tooltip', () => {
    const model = jaccardMatrix(FIXTURES.jaccard_similarity_pair);
    expect(model.ids).toEqual(['400405', '14923']);
    const cell = model.cells.find((c) => c.row === '400405' && c.col === '14923');
    const mirror = model.cells.find((c) => c.row === '14923' && c.col === '400405');
    expect(cell?.value).toBeCloseTo(0.1837, 3);
    expect(mirror?.value).toBe(cell?.value);
    const rows = Object.fromEntries((cell?.tooltip.rows ?? []).map((r) => [r.label, r.value]));
    expect(cell?.tooltip.title).toBe('GS400405 vs GS14923');
    expect(rows['p-value']).toBe('0.002');
    expect(rows['Significant at p ≤ 0.05']).toBe('yes');
    expect(rows['Shared genes']).toBe('9');
    // Oriented to the cell: the mirrored cell swaps "only in" counts with the labels.
    const mirrorRows = Object.fromEntries((mirror?.tooltip.rows ?? []).map((r) => [r.label, r.value]));
    expect(rows['Only in GS400405']).toBe(mirrorRows['Only in GS400405']);
    expect(rows['Only in GS400405']).toBe('22');
    expect(rows['Only in GS14923']).toBe('18');
    expect(model.cells.filter((c) => c.row === c.col).every((c) => c.value === null)).toBe(true);
  });

  it('JaccardSimilarity: every pair of five gene sets is drawn, both ways', () => {
    const model = jaccardMatrix(FIXTURES.jaccard_similarity);
    expect(model.cells).toHaveLength(5 + 2 * 10);
  });

  it('HyperGeometric: -log10 p, finite even for p = 0, scale fitted to the data', () => {
    const model = hypergeometricMatrix(FIXTURES.hypergeometric);
    const values = model.cells.map((c) => c.value).filter((v): v is number => v !== null);
    expect(values.every(Number.isFinite)).toBe(true);
    expect(model.domain[1]).toBe(Math.max(...values));
    // The strongest pair in this data is ~1e-25.
    expect(model.domain[1]).toBeGreaterThan(20);
    expect(hypergeometricMatrix({ geneset_ids: ['a', 'b'], results: [{ i: 0, j: 1, upper_tail: 0, odds_ratio: null }] }).domain[1]).toBe(300);
    const cell = model.cells.find((c) => c.row !== c.col)!;
    expect(cell.tooltip.rows?.map((r) => r.label)).toEqual([
      'Upper-tail p (more shared than chance)',
      'Lower-tail p (fewer shared)',
      'Two-tailed p',
      'Odds ratio',
    ]);
  });
});

describe('dendrogramModel', () => {
  it('keeps every gene set as a leaf, with merge distances as heights', () => {
    const tree = dendrogramModel(FIXTURES.jaccard_clustering.tree);
    const leaves: string[] = [];
    const walk = (node: { name: string; height: number; children?: unknown[] }) => {
      if (!node.children) {
        leaves.push(node.name);
        expect(node.height).toBe(0);
      } else {
        (node.children as typeof node[]).forEach(walk);
      }
    };
    walk(tree!);
    expect(leaves.sort()).toEqual(
      FIXTURES.jaccard_clustering.geneset_ids.map((id: string) => `GS${id}`).sort(),
    );
    expect(tree!.height).toBeCloseTo(FIXTURES.jaccard_clustering.tree.distance, 6);
  });

  it('has nothing to draw without a tree', () => {
    expect(dendrogramModel(null)).toBeNull();
  });
});

describe('dbscanModel', () => {
  it('groups genes by cluster for packing', () => {
    const model = dbscanModel(FIXTURES.dbscan);
    expect(model?.children).toHaveLength(FIXTURES.dbscan.clusters.length);
    expect(model?.children?.[0].children?.[0]).toEqual({ name: FIXTURES.dbscan.clusters[0][0], value: 1 });
  });

  it('has nothing to draw when the tool declined to run', () => {
    expect(dbscanModel({ ran: false, clusters: [] })).toBeNull();
  });
});

describe('booleanModel', () => {
  const output = FIXTURES.boolean_algebra as unknown as BooleanAlgebraOutput;

  it('counts distinct gene sets per gene, not identifier rows', () => {
    const model = booleanModel(output);
    for (const gene of model.result) {
      expect(new Set(gene.sets).size).toBe(gene.sets.length);
    }
    // circle_groups lists a set once per identifier: [233535, 233535] is one set.
    const single = Object.entries(output.circle_groups!).find(
      ([, groups]) => new Set(groups).size === 1 && groups.length > 1,
    )!;
    expect(model.result.find((g) => g.key === single[0])?.sets).toEqual([single[1][0]]);
  });

  it('labels genes by symbol, not by UniGene id', () => {
    const labels = booleanModel(output).result.map((g) => g.label);
    expect(labels.some((label) => /^[A-Z][a-z]\.\d+$/.test(label))).toBe(false);
  });

  it("surfaces genes the tool returned for an intersection that are in too few sets", () => {
    // On dev, intersection over five sets returned 447 genes but only 95 are in >= 2 sets:
    // the tool counts identifier rows. The view must say so rather than hide it.
    const model = booleanModel(output);
    expect(model.relation.toLowerCase()).toBe('intersection');
    expect(model.belowThreshold).toBe(model.result.filter((g) => g.sets.length < 2).length);
    expect(model.belowThreshold).toBeGreaterThan(0);
    expect(FIXTURES.boolean_algebra_full_counts).toEqual({ genes: 448, in_two_or_more: 95, intersect_keys: 447 });
  });

  it('union answers every gene; combinations count exact membership', () => {
    const model = booleanModel({ ...output, relation: 'Union' });
    expect(model.result).toHaveLength(Object.keys(output.bool_results).length);
    expect(model.belowThreshold).toBe(0);
    expect(model.combinations.reduce((sum, c) => sum + c.size, 0)).toBe(model.result.length);
  });
});

describe('Venn geometry', () => {
  it('lensArea spans no overlap to full containment', () => {
    expect(lensArea(1, 1, 2)).toBe(0);
    expect(lensArea(1, 2, 0.5)).toBeCloseTo(Math.PI, 10);
  });

  it('places two circles so their overlap area matches the shared count', () => {
    const r1 = Math.sqrt(74 / Math.PI);
    const r2 = Math.sqrt(84 / Math.PI);
    const d = distanceForOverlap(r1, r2, 45);
    expect(lensArea(r1, r2, d)).toBeCloseTo(45, 4);
  });

  it('lays out 2 or 3 sets with areas proportional to size, and refuses 4', () => {
    const shared = () => 10;
    const two = vennLayout([{ id: 1, size: 74 }, { id: 2, size: 84 }], shared)!;
    expect(Math.PI * two[0].r ** 2).toBeCloseTo(74, 6);
    const three = vennLayout(
      [{ id: 1, size: 74 }, { id: 2, size: 84 }, { id: 3, size: 59 }],
      shared,
    )!;
    expect(three).toHaveLength(3);
    const d = Math.hypot(three[0].x - three[2].x, three[0].y - three[2].y);
    expect(lensArea(three[0].r, three[2].r, d)).toBeCloseTo(10, 3);
    expect(vennLayout([1, 2, 3, 4].map((id) => ({ id, size: 10 })), shared)).toBeNull();
  });
});

describe('msetModel', () => {
  it('reads the null distribution and the observed overlap', () => {
    const model = msetModel(FIXTURES.mset);
    expect(model.bins).toEqual([
      { overlap: 0, share: 0.911 },
      { overlap: 1, share: 0.084 },
      { overlap: 2, share: 0.005 },
    ]);
    expect(model.observed).toBe(45);
    // 0 of 1000 trials bounds p by 1/1000; it is not an exact 0.
    expect(model.pValue).toBe('< 0.001 (no sample as extreme)');
    expect(model.trials).toBe('1000');
  });
});

describe('phenomeMapElements', () => {
  it('a node per displayed biclique, an edge per link between displayed ones', () => {
    const elements = phenomeMapElements(FIXTURES.phenome_map);
    const nodes = elements.filter((e) => e.group === 'nodes');
    const edges = elements.filter((e) => e.group === 'edges');
    expect(nodes).toHaveLength(26);
    const ids = new Set(nodes.map((n) => n.data['id']));
    expect(edges.every((e) => ids.has(e.data['source']) && ids.has(e.data['target']))).toBe(true);
    expect(edges.length).toBeGreaterThan(0);
  });

  it('puts each biclique on its own level\'s row, every link pointing down', () => {
    const elements = phenomeMapElements(FIXTURES.phenome_map);
    const y = new Map(
      elements.filter((e) => e.group === 'nodes').map((n) => [n.data['id'], n.position!.y]),
    );
    const rows = new Set(y.values());
    expect(rows.size).toBe(new Set(FIXTURES.phenome_map.nodes.map((n) => n.depth)).size);
    for (const edge of elements.filter((e) => e.group === 'edges')) {
      expect(y.get(edge.data['target'])!).toBeGreaterThan(y.get(edge.data['source'])!);
    }
  });

  it('orders a row by where its parents sit, to cut crossings', () => {
    const positions = phenomeMapPositions([
      { id: 1, genesets: [], genes: [], depth: 0, children: [{ target: 4, score: 1 }] },
      { id: 2, genesets: [], genes: [], depth: 0, children: [{ target: 3, score: 1 }] },
      { id: 3, genesets: [], genes: [], depth: 1 },
      { id: 4, genesets: [], genes: [], depth: 1 },
    ]);
    // 1 is left of 2, so 1's child (4) goes left of 2's child (3).
    expect(positions.get(4)!.x).toBeLessThan(positions.get(3)!.x);
  });

  it('does not single out every node when the tool flagged them all', () => {
    // With no emphasis genes the tool sets `emphasize` on every node.
    const all = phenomeMapElements(FIXTURES.phenome_map).filter((e) => e.group === 'nodes');
    expect(FIXTURES.phenome_map.nodes.every((n) => n.emphasize)).toBe(true);
    expect(all.some((n) => n.data['emphasize'])).toBe(false);
    const some = phenomeMapElements({
      nodes: [
        { id: 1, genesets: ['a'], genes: ['x'], depth: 0, emphasize: true },
        { id: 2, genesets: ['b'], genes: ['y'], depth: 0, emphasize: false },
      ],
    });
    expect(some.map((n) => n.data['emphasize'])).toEqual([true, false]);
  });

  it('says "1 set", not "1 sets"', () => {
    const [node] = phenomeMapElements({
      nodes: [{ id: 1, genesets: ['a'], genes: ['x'], depth: 0 }],
    });
    expect(node.data['label']).toBe('1 set · 1 gene');
  });

  it('leaves out hidden nodes and the links touching them', () => {
    const elements = phenomeMapElements({
      nodes: [
        { id: 1, genesets: ['a', 'b'], genes: ['x'], depth: 0, children: [{ target: 2, score: 0.5 }] },
        { id: 2, genesets: ['a'], genes: ['x', 'y'], depth: 1, displayed: false },
      ],
    });
    expect(elements.map((e) => e.data['id'])).toEqual(['n1']);
  });
});

describe('combineModel', () => {
  it('a row per gene, a column per gene set, named, most-shared first', () => {
    const model = combineModel(FIXTURES.combine);
    expect(model.columns.map((c) => c.id)).toEqual(FIXTURES.combine.geneset_ids.map(String));
    expect(model.columns[0].label).not.toMatch(/^GS/);
    const counts = model.rows.map((r) => r.count);
    expect(counts).toEqual([...counts].sort((a, b) => b - a));
    expect(model.rows.every((r) => r.count >= 1)).toBe(true);
  });
});
