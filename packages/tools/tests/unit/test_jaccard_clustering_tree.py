"""Tests for building the dendrogram without SciPy's `to_tree`.

`to_tree` validates through SciPy's array-API compatibility layer, which probes for
Google's JAX with ``getattr(sys.modules["jax"], "Array")``. Here ``jax`` is a namespace
package from *Jackson Laboratory's* ``jax-apiutils``, so that attribute is absent and SciPy
raises ``AttributeError: module 'jax' has no attribute 'Array'``. The GeneWeaver API imports
``jax.apiutils`` on every request path, so the tool failed there while passing in a bare
script -- which is why this is tested rather than assumed.
"""

import random
import subprocess
import sys

import pytest

pytest.importorskip("scipy", reason="JaccardClustering needs the sklearn extra")

import numpy as np
from geneweaver.tools.jaccard_clustering.tool import (
    _tree_from_linkage,
    cluster_tree,
)
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform


def _random_similarity(size: int, seed: int) -> list[list[float]]:
    random.seed(seed)
    matrix = [[0.0] * size for _ in range(size)]
    for i in range(size):
        matrix[i][i] = 1.0
        for j in range(i + 1, size):
            matrix[i][j] = matrix[j][i] = random.random()
    return matrix


def _shape(node) -> tuple:
    """Tree as nested tuples, for comparison."""
    if node.geneset_id is not None:
        return ("leaf", node.geneset_id)
    return (
        "node",
        round(float(node.distance), 12),
        _shape(node.children[0]),
        _shape(node.children[1]),
    )


def test_it_works_with_jax_apiutils_imported() -> None:
    """The condition that broke it: the API imports this on every request."""
    import jax.apiutils  # noqa: F401

    tree = cluster_tree(_random_similarity(5, 1), "average", [f"gs{i}" for i in range(5)])
    assert tree is not None
    assert _shape(tree)[0] == "node"


def test_matches_scipys_own_to_tree() -> None:
    """Equivalence with the implementation this replaced, across methods and sizes.

    Run in a subprocess, because the comparison needs SciPy's `to_tree` to *work* -- and it
    does not work in a process where the conflicting `jax` namespace has been imported,
    which is the whole reason for this module. The child blanks `sys.modules["jax"]` before
    importing SciPy so the oracle is usable, then imports our builder and compares.
    """
    script = """
import random, sys
sys.modules["jax"] = None  # keep SciPy's array-API probe away from jax-apiutils
import numpy as np
from scipy.cluster.hierarchy import linkage, to_tree
from scipy.spatial.distance import squareform
del sys.modules["jax"]
from geneweaver.tools.jaccard_clustering.tool import _METHOD_MAP, _tree_from_linkage

def oracle(node, ids):
    if node.is_leaf():
        return ("leaf", ids[node.id])
    return ("node", round(float(node.dist), 12),
            oracle(node.get_left(), ids), oracle(node.get_right(), ids))

def ours(node):
    if node.geneset_id is not None:
        return ("leaf", node.geneset_id)
    return ("node", round(float(node.distance), 12), ours(node.children[0]), ours(node.children[1]))

random.seed(3)
compared = 0
for _ in range(40):
    size = random.randint(2, 12)
    ids = [f"gs{i}" for i in range(size)]
    matrix = np.zeros((size, size))
    for i in range(size):
        for j in range(i + 1, size):
            matrix[i][j] = matrix[j][i] = random.random()
    condensed = squareform(matrix, checks=False)
    for method in _METHOD_MAP.values():
        Z = linkage(condensed, method=method)
        assert oracle(to_tree(Z), ids) == ours(_tree_from_linkage(Z, ids)), (size, method)
        compared += 1
print(compared)
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=300
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert int(result.stdout.strip()) >= 200, "too few comparisons to be meaningful"


def test_scipys_to_tree_is_what_breaks_not_our_builder() -> None:
    """Pins the diagnosis, so a future reader does not undo the workaround.

    With `jax.apiutils` imported, SciPy's own `to_tree` raises while ours works on the same
    linkage matrix. If SciPy or jax-apiutils ever fixes this, this test fails and the
    workaround can go.
    """
    import jax.apiutils  # noqa: F401
    from scipy.cluster.hierarchy import to_tree

    geneset_ids = [f"gs{i}" for i in range(4)]
    similarity = np.asarray(_random_similarity(4, 2), dtype=float)
    distance = 1.0 - similarity
    np.fill_diagonal(distance, 0.0)
    linkage_matrix = linkage(squareform((distance + distance.T) / 2.0, checks=False), "average")

    with pytest.raises(AttributeError, match="jax"):
        to_tree(linkage_matrix)

    assert _tree_from_linkage(linkage_matrix, geneset_ids) is not None


def test_fewer_than_two_genesets_has_no_tree() -> None:
    """One gene set cannot be clustered; the tool reports no tree rather than failing."""
    assert cluster_tree([[1.0]], "average", ["gs0"]) is None


def test_leaves_cover_every_geneset_exactly_once() -> None:
    """A dropped or duplicated leaf would silently misreport the clustering."""
    geneset_ids = [f"gs{i}" for i in range(9)]
    tree = cluster_tree(_random_similarity(9, 7), "complete", geneset_ids)

    leaves: list[str] = []
    stack = [tree]
    while stack:
        node = stack.pop()
        if node.geneset_id is not None:
            leaves.append(node.geneset_id)
        else:
            stack.extend(node.children)
    assert sorted(leaves) == sorted(geneset_ids)
