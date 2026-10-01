"""Building each tool's input from resolved gene-set memberships.

The tools are pure: each takes a fully-built input and touches no database. Something has
to assemble that input, and the shape differs per tool -- a membership dict for UpSet and
DBSCAN, 2x2 contingency tables for HyperGeometric, a similarity matrix for
JaccardClustering, legacy row tuples for Combine. This module owns those assemblies.

Split by what they need:

* the functions here are **pure** -- they derive everything from memberships already
  fetched, so they are trivially testable and run no queries;
* anything needing more database state (homology, Jaccard null distributions) is resolved
  in ``geneweaver.db.tool_input`` and passed in.

`_pairs` fixes the pair ordering once. HyperGeometric and JaccardSimilarity both index
their results by position into ``geneset_ids``, so the order the pairs are generated in is
part of the contract with the caller, not an implementation detail.
"""

import itertools


def _pairs(count: int) -> list[tuple[int, int]]:
    """Index pairs (i < j) in the order both pairwise tools report their results."""
    return list(itertools.combinations(range(count), 2))


def ordered_memberships(
    memberships: dict[str, list[str]], geneset_ids: list[int]
) -> list[set[str]]:
    """Memberships as sets, in the caller's gene-set order.

    Deduplicates: a gene set can list the same symbol twice when two identifiers map to one
    gene, and every count below is a set operation. (The same conflation inflated `gs_count`
    in GWC-34.)
    """
    return [set(memberships.get(str(geneset_id), [])) for geneset_id in geneset_ids]


def contingency_pairs(
    memberships: dict[str, list[str]], geneset_ids: list[int]
) -> list[dict[str, int]]:
    """2x2 contingency tables per gene-set pair, for HyperGeometric.

    The universe is the **union of the gene sets in this request**, which is what legacy
    did and what `scripts/validation/validate_hypergeometric.py` validates against. It is
    deliberately not the species gene space: that would be a different test, and the port
    was verified against the former.

    ``f11`` is the overlap, ``f10``/``f01`` the exclusive parts, ``f00`` everything in the
    universe that is in neither set.
    """
    sets = ordered_memberships(memberships, geneset_ids)
    universe = set().union(*sets) if sets else set()
    return [
        {
            "i": i,
            "j": j,
            "f11": len(sets[i] & sets[j]),
            "f10": len(sets[i] - sets[j]),
            "f01": len(sets[j] - sets[i]),
            "f00": len(universe) - len(sets[i] | sets[j]),
        }
        for i, j in _pairs(len(sets))
    ]


def jaccard_pair_counts(
    memberships: dict[str, list[str]], geneset_ids: list[int]
) -> list[dict[str, int]]:
    """Per-pair overlap counts, for JaccardSimilarity."""
    sets = ordered_memberships(memberships, geneset_ids)
    return [
        {
            "i": i,
            "j": j,
            "only_i": len(sets[i] - sets[j]),
            "only_j": len(sets[j] - sets[i]),
            "intersection": len(sets[i] & sets[j]),
        }
        for i, j in _pairs(len(sets))
    ]


def similarity_matrix(
    memberships: dict[str, list[str]], geneset_ids: list[int]
) -> list[list[float]]:
    """Full symmetric Jaccard similarity matrix, for JaccardClustering.

    Diagonal is 1.0; a pair of empty sets is 0.0 rather than undefined, so an empty gene
    set clusters as maximally dissimilar instead of raising.
    """
    sets = ordered_memberships(memberships, geneset_ids)
    size = len(sets)
    matrix = [[0.0] * size for _ in range(size)]
    for index in range(size):
        matrix[index][index] = 1.0
    for i, j in _pairs(size):
        union = len(sets[i] | sets[j])
        value = (len(sets[i] & sets[j]) / union) if union else 0.0
        matrix[i][j] = matrix[j][i] = value
    return matrix
