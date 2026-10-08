import { FIXTURES } from './fixtures';
import {
  booleanModel,
  BooleanAlgebraOutput,
  combineModel,
  dbscanModel,
  dbscanNetwork,
  dendrogramModel,
  distanceForOverlap,
  formatEmpiricalP,
  formatP,
  hypergeometricMatrix,
  jaccardMatrix,
  jaccardVennGrid,
  lensArea,
  msetEuler,
  msetModel,
  phenomeMapElements,
  phenomeMapMatches,
  phenomeMapPositions,
  phenomeMapStats,
  speciesSummary,
  sunburstArcs,
  upsetModel,
  vennCellGreyed,
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
    expect(formatEmpiricalP(0)).toBe('≈ 0 (no sample as extreme)');
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

  it('JaccardSimilarity: a p of 0 means no null distribution, never "significant"', () => {
    // The tool returns 0.0 only when no distribution covers the pair; a computed p counts
    // the observation itself, so it is never 0. 9 of these 10 dev pairs are uncovered.
    const model = jaccardMatrix(FIXTURES.jaccard_similarity);
    const zero = FIXTURES.jaccard_similarity.results.find((r) => r.p_value === 0)!;
    const cell = model.cells.find(
      (c) => c.row === model.ids[zero.i] && c.col === model.ids[zero.j],
    )!;
    const rows = Object.fromEntries((cell.tooltip.rows ?? []).map((r) => [r.label, r.value]));
    expect(rows['p-value']).toBe('none');
    expect(Object.keys(rows).some((label) => label.startsWith('Significant'))).toBe(false);
    expect(cell.tooltip.note).toContain('no p-value');
    expect(FIXTURES.jaccard_similarity.results.filter((r) => r.p_value === 0)).toHaveLength(9);
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

  it('Except: counts single-set genes the tool dropped, which it would otherwise hide', () => {
    // Gene "dup" is only in set 1, but has two identifier rows there; the tool's
    // row-counting `bool_except` drops it (G3-830). "solo" has one row and is kept.
    const model = booleanModel({
      relation: 'Except',
      at_least: 2,
      geneset_ids: [1, 2],
      bool_results: {
        dup: [[10, 'Ppp1ccb', 1, 1], [10, 'Mm.334198', 1, 1]],
        solo: [[11, 'Kit', 1, 2]],
        both: [[12, 'Drd2', 1, 1], [12, 'Drd2', 1, 2]],
      },
      circle_groups: { dup: [1, 1], solo: [2], both: [1, 2] },
      bool_except: { '1': { solo: [[11, 'Kit', 1, 2]] } },
    });
    expect(model.result.map((g) => g.key)).toEqual(['solo']);
    expect(model.missingFromExcept).toBe(1);
    expect(model.belowThreshold).toBe(0);
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

describe('jaccardVennGrid', () => {
  const grid = jaccardVennGrid(FIXTURES.jaccard_similarity);
  const n = FIXTURES.jaccard_similarity.geneset_ids.length;

  it('a cell per ordered pair and one per diagonal, rows and columns in run order', () => {
    expect(grid.cells).toHaveLength(n * n);
    expect(grid.cells.filter((c) => c.diagonal)).toHaveLength(n);
    expect(grid.ids).toEqual(FIXTURES.jaccard_similarity.geneset_ids);
  });

  it('derives each set size from its pairs, agreeing across them', () => {
    for (const r of FIXTURES.jaccard_similarity.results) {
      const [a, b] = [grid.ids[r.i], grid.ids[r.j]];
      expect(grid.sizes[a]).toBe(r.intersection + r.only_i);
      expect(grid.sizes[b]).toBe(r.intersection + r.only_j);
    }
  });

  it('orients counts by cell: below the diagonal the row set is the pair\'s second set', () => {
    const r = FIXTURES.jaccard_similarity.results[0];
    const above = grid.cells.find((c) => c.row === grid.ids[r.i] && c.col === grid.ids[r.j])!;
    const below = grid.cells.find((c) => c.row === grid.ids[r.j] && c.col === grid.ids[r.i])!;
    expect([above.onlyRow, above.onlyCol]).toEqual([r.only_i, r.only_j]);
    expect([below.onlyRow, below.onlyCol]).toEqual([r.only_j, r.only_i]);
    expect(above.lines[0]).toBe(`(${r.only_i} ${r.intersection} ${r.only_j})`);
    expect(above.lines[1]).toBe(`J = ${r.jaccard.toFixed(3)}`);
  });

  it('circles: areas in proportion to the sizes, lens to the shared genes, inside the cell', () => {
    const pair = jaccardVennGrid(FIXTURES.jaccard_similarity_pair);
    const cell = pair.cells.find((c) => !c.diagonal)!;
    const [a, b] = cell.circles;
    expect((a.r / b.r) ** 2).toBeCloseTo(cell.rowSize / cell.colSize, 6);
    const scale = a.r / Math.sqrt(cell.rowSize / Math.PI);
    const lens = lensArea(a.r, b.r, b.cx - a.cx) / scale ** 2;
    expect(lens).toBeCloseTo(cell.shared, 3);
    for (const c of cell.circles) {
      expect(c.cx - c.r).toBeGreaterThanOrEqual(0);
      expect(c.cx + c.r).toBeLessThanOrEqual(1);
    }
  });

  it('a pair with no p-value reads "none"; one with a p-value shows it', () => {
    const none = grid.cells.find((c) => !c.diagonal && c.p === null)!;
    expect(none.lines[2]).toBe('p = none');
    const pair = jaccardVennGrid(FIXTURES.jaccard_similarity_pair).cells.find((c) => !c.diagonal)!;
    expect(pair.lines[2]).toBe('p = 0.002');
  });

  it('greys pairs above the threshold or without a p-value, but nothing at 1.0', () => {
    const cell = jaccardVennGrid(FIXTURES.jaccard_similarity_pair).cells.find((c) => !c.diagonal)!;
    expect(vennCellGreyed(cell, 0.05)).toBe(false);
    expect(vennCellGreyed(cell, 0.001)).toBe(true);
    const none = grid.cells.find((c) => !c.diagonal && c.p === null)!;
    expect(vennCellGreyed(none, 0.5)).toBe(true);
    expect(vennCellGreyed(none, 1)).toBe(false);
    expect(grid.cells.filter((c) => c.diagonal).some((c) => vennCellGreyed(c, 0.01))).toBe(false);
  });

  it('starts from the threshold the run used', () => {
    expect(grid.threshold).toBe(FIXTURES.jaccard_similarity.p_value_threshold);
  });
});

describe('sunburstArcs', () => {
  const tree = dendrogramModel(FIXTURES.jaccard_clustering.tree);
  const arcs = sunburstArcs(tree);
  const leaves = arcs.filter((a) => a.leaf);

  it('an arc per gene set, together covering the full circle once', () => {
    expect(leaves.map((a) => a.name).sort()).toEqual(
      FIXTURES.jaccard_clustering.geneset_ids.map((id) => `GS${id}`).sort(),
    );
    const span = leaves.reduce((sum, a) => sum + (a.end - a.start), 0);
    expect(span).toBeCloseTo(2 * Math.PI, 9);
  });

  it('each cluster spans exactly its gene sets, with its similarity', () => {
    for (const cluster of arcs.filter((a) => !a.leaf)) {
      const inside = leaves.filter((a) => a.start >= cluster.start - 1e-9 && a.end <= cluster.end + 1e-9);
      expect(inside.map((a) => a.name).sort()).toEqual([...cluster.members].sort());
      expect(cluster.similarity).toBeGreaterThanOrEqual(0);
      expect(cluster.similarity).toBeLessThanOrEqual(1);
    }
  });

  it('nothing for no tree', () => {
    expect(sunburstArcs(null)).toEqual([]);
  });
});

describe('dbscanNetwork', () => {
  it('links genes sharing a gene set, coloured by cluster, from the real memberships', () => {
    const network = dbscanNetwork(FIXTURES.dbscan);
    expect(network.available).toBe(true);
    expect(network.nodes).toHaveLength(12);
    expect(network.nodes.every((n) => n.cluster === 0)).toBe(true);
    // Cnr1 is in 167180, 378899 and 164706; Gnaz in 167180 and 164706: two shared sets.
    const edge = network.edges.find(
      (e) => [e.source, e.target].sort().join() === ['Cnr1', 'Gnaz'].join(),
    )!;
    expect(edge.genesets.sort()).toEqual(['164706', '167180']);
    // All 12 are in 167180, so every pair is linked once.
    expect(network.edges).toHaveLength((12 * 11) / 2);
  });

  it('genes in no cluster are noise', () => {
    const network = dbscanNetwork({
      ran: true,
      clusters: [['A', 'B']],
      gene_genesets: { A: ['1'], B: ['1'], C: ['2'] },
    });
    expect(network.nodes.find((n) => n.id === 'C')?.cluster).toBeNull();
    expect(network.edges).toEqual([{ source: 'A', target: 'B', genesets: ['1'] }]);
  });

  it('refuses past the edge budget instead of drawing a hairball', () => {
    const genes = Array.from({ length: 30 }, (_, i) => `G${i}`);
    const network = dbscanNetwork(
      { ran: true, clusters: [genes], gene_genesets: Object.fromEntries(genes.map((g) => [g, ['1']])) },
      100,
    );
    expect(network.tooLarge).toBe(true);
    expect(network.edges).toEqual([]);
  });

  it('says so when the result has no memberships (an older worker)', () => {
    const network = dbscanNetwork({ ran: true, clusters: [['A']] });
    expect(network.available).toBe(false);
  });
});

describe('msetEuler', () => {
  it('areas proportional to gene counts, the lens to the shared genes', () => {
    const euler = msetEuler(FIXTURES.mset)!;
    expect(euler).toMatchObject({ universe: 66866, list1: 74, list2: 84, shared: 45 });
    expect(Math.PI * euler.r1 ** 2).toBeCloseTo((Math.PI * 74) / 66866, 12);
    expect(lensArea(euler.r1, euler.r2, euler.distance)).toBeCloseTo((Math.PI * 45) / 66866, 9);
  });

  it('null when the summary lacks the counts', () => {
    expect(msetEuler({ mset_data: { 'P-Value': '0.1' } })).toBeNull();
  });
});

describe('speciesSummary', () => {
  it('per species: genes only there, genes matched in another, and the total', () => {
    const rows = speciesSummary({
      relation: 'Union',
      at_least: 2,
      geneset_ids: [10, 20],
      // Keyed by homology group across species; a negative key is a gene with no homolog.
      bool_results: {
        '7': [[1, 'Drd2', 1, 10], [2, 'DRD2', 2, 20]],
        '8': [[3, 'Kit', 1, 10]],
        '-4': [[4, 'XYZ', 2, 20]],
        '9': [[5, 'Tyr', 1, 10], [6, 'TYR', 2, 20]],
      },
    })!;
    expect(rows).toEqual([
      { species: 1, name: 'Mouse', specific: 1, shared: 2, total: 3 },
      { species: 2, name: 'Human', specific: 1, shared: 2, total: 3 },
    ]);
  });

  it('null for a single species, where the table would say nothing', () => {
    expect(speciesSummary(FIXTURES.boolean_algebra as unknown as BooleanAlgebraOutput)).toBeNull();
  });
});

describe('phenomeMapMatches and phenomeMapStats', () => {
  const nodes = FIXTURES.phenome_map.nodes;

  it('finds the bicliques holding a gene, ignoring case, or a gene set, with or without GS', () => {
    const top = nodes.find((n) => n.depth === 0)!;
    const gene = top.genes[0];
    const byGene = phenomeMapMatches(nodes, gene.toUpperCase());
    expect(byGene.has(top.id)).toBe(true);
    expect([...byGene].every((id) => nodes.find((n) => n.id === id)!.genes.includes(gene))).toBe(true);

    const set = top.genesets[0];
    expect(phenomeMapMatches(nodes, `GS${set}`)).toEqual(phenomeMapMatches(nodes, set));
    expect(phenomeMapMatches(nodes, 'NoSuchGene').size).toBe(0);
    expect(phenomeMapMatches(nodes, '  ').size).toBe(0);
  });

  it('matches any of several terms', () => {
    const [a, b] = [nodes[0].genes[0], nodes[nodes.length - 1].genes[0]];
    const both = phenomeMapMatches(nodes, `${a}, ${b}`);
    for (const id of [...phenomeMapMatches(nodes, a), ...phenomeMapMatches(nodes, b)]) {
      expect(both.has(id)).toBe(true);
    }
  });

  it('the stats legacy showed, from the result', () => {
    const stats = Object.fromEntries(phenomeMapStats(FIXTURES.phenome_map).map((r) => [r.label, r.value]));
    expect(stats['Gene sets']).toBe('5');
    expect(stats['Genes']).toBe('448');
    expect(stats['Bicliques shown']).toBe('26');
    expect(stats['Levels']).toBe('5');
  });
});
