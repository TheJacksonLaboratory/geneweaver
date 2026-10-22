import { groupA, groupB, toggleGroupB, tricliqueGroupProblem } from './triclique-groups';

describe('triclique groups', () => {
  it('splits the run into the marked gene sets and the rest', () => {
    expect(groupB([1, 2, 3], [3])).toEqual([3]);
    expect(groupA([1, 2, 3], [3])).toEqual([1, 2]);
  });

  it('forgets a mark once its gene set leaves the run', () => {
    expect(groupB([1, 2], [3, 2])).toEqual([2]);
  });

  it('needs a gene set in each group, but says nothing before two are in', () => {
    expect(tricliqueGroupProblem([1], [])).toBeUndefined();
    expect(tricliqueGroupProblem([1, 2], [])).toContain('group B');
    expect(tricliqueGroupProblem([1, 2], [1, 2])).toContain('group A');
    expect(tricliqueGroupProblem([1, 2], [2])).toBeUndefined();
  });

  it('toggles a mark', () => {
    expect(toggleGroupB([1], 2)).toEqual([1, 2]);
    expect(toggleGroupB([1, 2], 1)).toEqual([2]);
  });
});
