/**
 * Triclique's two groups. Legacy compared two projects; v3 has none, so the run's gene sets
 * are split instead: the user marks group B's, and every other gene set is group A. The API
 * takes the same split (`parameters.group_b`).
 */

/** Group B as marked, less any gene set no longer in the run. */
export function groupB(genesetIds: number[], marked: number[]): number[] {
  const inRun = new Set(genesetIds);
  return marked.filter((id) => inRun.has(id));
}

/** Group A: the run's gene sets not marked as B. */
export function groupA(genesetIds: number[], marked: number[]): number[] {
  const b = new Set(marked);
  return genesetIds.filter((id) => !b.has(id));
}

/** Why the split cannot be run, or `undefined` if it can. Silent until two gene sets are in. */
export function tricliqueGroupProblem(genesetIds: number[], marked: number[]): string | undefined {
  if (genesetIds.length < 2) {
    return undefined;
  }
  if (!groupB(genesetIds, marked).length) {
    return 'Mark at least one gene set as group B: Triclique compares two groups.';
  }
  if (!groupA(genesetIds, marked).length) {
    return 'Leave at least one gene set in group A: Triclique compares two groups.';
  }
  return undefined;
}

/** Mark or unmark a gene set as group B. */
export function toggleGroupB(marked: number[], id: number): number[] {
  return marked.includes(id) ? marked.filter((value) => value !== id) : [...marked, id];
}
