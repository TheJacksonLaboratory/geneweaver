"""Input/output schemas for the PhenomeMap tool."""

from __future__ import annotations

from geneweaver.tools.framework.schema import ToolInput, ToolOutput
from pydantic import BaseModel, Field


class PhenomeMapInput(ToolInput):
    """Input for PhenomeMap (maximal-biclique intersection graph of gene sets).

    ``gene_sets`` is the bipartite graph: ``geneset_id -> [member gene ids]``. The tool
    enumerates the maximal bicliques (maximal sets of gene sets that share a maximal set of
    genes), links each biclique to its descendant bicliques (those over a proper subset of
    the gene sets), and scores each link.

    ``gene_ranks`` (``gene_id -> rank``) feeds the Kolmogorov-Smirnov term of the link score;
    when it is empty the score collapses to the gene-count ratio alone (no scipy needed).
    """

    gene_sets: dict[str, list[str]] = Field(default_factory=dict)
    gene_ranks: dict[str, float] = Field(default_factory=dict)

    #: Minimum genes for a biclique to be kept.
    min_genes: int = 1
    #: Cut the tree below the smallest level whose width exceeds this (0 = no cut).
    max_level: int = 0
    #: Keep only links whose score is <= this threshold (>= ~1.0 disables trimming).
    p_value_threshold: float = 1.0
    #: Apply a Benjamini-Hochberg FDR correction to derive the link-score threshold.
    use_fdr: bool = False
    #: Skip bootstrap reduction even on large graphs.
    disable_bootstrap: bool = False
    #: Apply bootstrap reduction once the displayed-node count exceeds this.
    bootstrap_node_threshold: int = 100
    #: Gene ids to emphasize; a biclique containing any of them is flagged ``emphasize``.
    emphasis_genes: list[str] = Field(default_factory=list)


class BicliqueLink(BaseModel):
    """A directed link from a biclique to a descendant biclique, with its score."""

    target: int
    score: float


class BicliqueNode(BaseModel):
    """One maximal biclique: the gene sets it spans and the genes they share."""

    id: int
    genesets: list[str]
    genes: list[str]
    depth: int
    displayed: bool = True
    emphasize: bool = False
    #: ids of the immediate parent bicliques (those spanning a proper superset of gene sets).
    parents: list[int] = Field(default_factory=list)
    #: immediate child bicliques (proper subset of gene sets) with link scores.
    children: list[BicliqueLink] = Field(default_factory=list)


class PhenomeMapOutput(ToolOutput):
    """The PhenomeMap intersection graph (nodes + links), minus all rendering."""

    nodes: list[BicliqueNode] = Field(default_factory=list)
    num_genes: int = 0
    num_genesets: int = 0
    cut_depth: int = 0
    bootstrap_applied: bool = False
    notes: list[str] = Field(default_factory=list)
