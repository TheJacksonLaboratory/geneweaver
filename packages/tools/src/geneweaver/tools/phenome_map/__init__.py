"""PhenomeMap tool (maximal-biclique intersection graph; wraps the biclique C binary)."""

from .schema import (
    BicliqueLink,
    BicliqueNode,
    PhenomeMapInput,
    PhenomeMapOutput,
)
from .tool import (
    PhenomeMap,
    build_edge_list,
    compute_subset_links,
    find_cut_depth,
    parse_bicliques,
    similarity,
    trim_links_by_score,
    trim_unconnected,
)

__all__ = [
    "BicliqueLink",
    "BicliqueNode",
    "PhenomeMap",
    "PhenomeMapInput",
    "PhenomeMapOutput",
    "build_edge_list",
    "compute_subset_links",
    "find_cut_depth",
    "parse_bicliques",
    "similarity",
    "trim_links_by_score",
    "trim_unconnected",
]
