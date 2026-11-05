"""Triclique (legacy TricliqueViewer): the largest clique across two groups of gene sets."""

from .schema import MAX_SHARED_GENES, Triclique, TricliqueInput, TricliqueOutput
from .tool import TricliqueTool, find_tricliques, tripartite_edges

__all__ = [
    "MAX_SHARED_GENES",
    "Triclique",
    "TricliqueInput",
    "TricliqueOutput",
    "TricliqueTool",
    "find_tricliques",
    "tripartite_edges",
]
