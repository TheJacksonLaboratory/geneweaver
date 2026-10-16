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
from dataclasses import dataclass


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


@dataclass(frozen=True)
class PairScope:
    """What one gene-set pair is counted over under pairwise deletion.

    ``genes`` restricts the count to genes both platforms can measure (None: every gene,
    which is the same-platform case); ``population`` is legacy's ``ref_count``, the
    HyperGeometric universe for the pair.
    """

    genes: frozenset[str] | None
    population: int


def deletion_platforms(geneset_ids: list[int], platforms: dict[int, tuple[int, int]]) -> set[int]:
    """The platforms pairwise deletion needs the gene space of, for this run.

    Only pairs of two platform-based gene sets (``gs_gene_id_type > 0``) of the same
    species are affected, so a run of gene-identifier sets queries nothing.
    """
    needed: set[int] = set()
    for i, j in _pairs(len(geneset_ids)):
        a, b = platforms.get(geneset_ids[i]), platforms.get(geneset_ids[j])
        if a and b and a[1] > 0 and b[1] > 0 and a[0] == b[0]:
            needed.update((a[1], b[1]))
    return needed


def pairwise_deletion_scopes(
    geneset_ids: list[int],
    platforms: dict[int, tuple[int, int]],
    platform_genes: dict[int, set[str]],
) -> dict[tuple[int, int], PairScope]:
    """Per-pair counting scopes, ported from legacy ``pairwise_deletion_counting``.

    For two gene sets measured on microarray platforms of the same species, a gene the
    other platform could not have measured says nothing about overlap, so legacy left it
    out of the pair's counts:

    * **different platforms** -- count only genes on both (``TOOLSET_SQL[6]``), over a
      population of that many genes;
    * **same platform** -- count every gene, over a population of the platform's genes
      (``TOOLSET_SQL[5]``).

    Any other pair -- a gene-identifier set, or two species -- is counted normally and has
    no entry here.

    :param geneset_ids: The gene sets, in the caller's order.
    :param platforms: ``{gs_id: (sp_id, gs_gene_id_type)}``.
    :param platform_genes: Each needed platform's gene symbols (:func:`deletion_platforms`).
    :return: ``{(i, j): PairScope}`` by index into ``geneset_ids``, ``i < j``.
    """
    scopes: dict[tuple[int, int], PairScope] = {}
    for i, j in _pairs(len(geneset_ids)):
        a, b = platforms.get(geneset_ids[i]), platforms.get(geneset_ids[j])
        if not (a and b and a[1] > 0 and b[1] > 0 and a[0] == b[0]):
            continue
        if a[1] == b[1]:
            scopes[(i, j)] = PairScope(None, len(platform_genes.get(a[1], ())))
        else:
            shared = frozenset(platform_genes.get(a[1], set()) & platform_genes.get(b[1], set()))
            scopes[(i, j)] = PairScope(shared, len(shared))
    return scopes


def _in_scope(member: str, genes: frozenset[str]) -> bool:
    """Whether a member is measurable, including a homology-merged ``"A/B"`` member."""
    return member in genes or ("/" in member and any(part in genes for part in member.split("/")))


def _scoped(
    sets: list[set[str]], i: int, j: int, scope: PairScope | None
) -> tuple[set[str], set[str]]:
    """The pair's two sets, restricted to the genes its scope counts."""
    if scope is None or scope.genes is None:
        return sets[i], sets[j]
    return (
        {member for member in sets[i] if _in_scope(member, scope.genes)},
        {member for member in sets[j] if _in_scope(member, scope.genes)},
    )


def contingency_pairs(
    memberships: dict[str, list[str]],
    geneset_ids: list[int],
    scopes: dict[tuple[int, int], PairScope] | None = None,
) -> list[dict[str, int]]:
    """2x2 contingency tables per gene-set pair, for HyperGeometric.

    The universe is the **union of the gene sets in this request**, which is what legacy
    did and what `scripts/validation/validate_hypergeometric.py` validates against. It is
    deliberately not the species gene space: that would be a different test, and the port
    was verified against the former.

    ``f11`` is the overlap, ``f10``/``f01`` the exclusive parts, ``f00`` everything in the
    universe that is in neither set.

    With pairwise deletion (``scopes``), a scoped pair counts only its measurable genes and
    its universe is the platform population instead, as legacy's ``ref_count`` was. Never
    negative: a member whose symbol is missing from the platform's mapping would otherwise
    push it below zero.
    """
    sets = ordered_memberships(memberships, geneset_ids)
    universe = set().union(*sets) if sets else set()
    scopes = scopes or {}
    tables = []
    for i, j in _pairs(len(sets)):
        scope = scopes.get((i, j))
        left, right = _scoped(sets, i, j, scope)
        population = scope.population if scope else len(universe)
        tables.append(
            {
                "i": i,
                "j": j,
                "f11": len(left & right),
                "f10": len(left - right),
                "f01": len(right - left),
                "f00": max(0, population - len(left | right)),
            }
        )
    return tables


def jaccard_pair_counts(
    memberships: dict[str, list[str]],
    geneset_ids: list[int],
    scopes: dict[tuple[int, int], PairScope] | None = None,
) -> list[dict[str, int]]:
    """Per-pair overlap counts, for JaccardSimilarity.

    With pairwise deletion (``scopes``), a pair on two different platforms counts only the
    genes both can measure; a same-platform pair is unchanged, since its population (which
    Jaccard does not use) is all that deletion alters there.
    """
    sets = ordered_memberships(memberships, geneset_ids)
    scopes = scopes or {}
    counts = []
    for i, j in _pairs(len(sets)):
        left, right = _scoped(sets, i, j, scopes.get((i, j)))
        counts.append(
            {
                "i": i,
                "j": j,
                "only_i": len(left - right),
                "only_j": len(right - left),
                "intersection": len(left & right),
            }
        )
    return counts


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
