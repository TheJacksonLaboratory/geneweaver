"""Faithful transcription of the legacy PhenomeMap in-memory post-processing.

Lifted verbatim (algorithm-wise) from legacy/tools-worker/tools/PhenomeMap.py lines
~55-446: the hand-rolled two-sample KS statistic, the ``similarity`` link score, the
subset-relationship pass, the p-value/FDR link trim, the cut-depth, and the
unconnected-node trim. DB lookups and all rendering are omitted.

Used only by validate_phenomemap.py to confirm the ported tool reproduces this behaviour.
It deliberately uses the legacy hand-rolled KS (NOT scipy) so the comparison also checks
the port's scipy-swap claim (scores must match to within a tight tolerance).
"""

from __future__ import annotations

import numpy as np

# --- legacy ks_2samp / ksprob (verbatim) -----------------------------------------------

KS_CONST = -((np.arange(1, 7, 2, dtype=float) * np.pi) ** 2) / 8


def ksprob(x):
    return 1 - np.sqrt(2 * np.pi) / x * np.sum(np.exp(KS_CONST / x**2))


def ks_2samp(data1, data2):
    data1 = np.asarray(data1)
    data2 = np.asarray(data2)
    data1.sort()
    data2.sort()
    n1, n2 = float(data1.size), float(data2.size)
    data_all = np.concatenate([data1, data2])
    cdf1 = np.searchsorted(data1, data_all, side="right") / n1
    cdf2 = np.searchsorted(data2, data_all, side="right") / n2
    d = np.max(np.absolute(cdf1 - cdf2))
    if d > np.finfo("float").eps:
        en = np.sqrt(n1 * n2 / (n1 + n2))
        prob = ksprob((en + 0.12 + 0.11 / en) * d)
    else:
        prob = 1.0
    return d, prob


class Biclique:
    def __init__(self, bid, gs, genes_dict):
        self.id = bid
        self.size = len(gs)
        self.genesets = gs
        self.num_genes = float(len(genes_dict))
        self.genes = set(genes_dict)
        self.ranks = list(genes_dict.values())
        self.displayed = True
        self.parents = {}
        self.children = {}

    def __hash__(self):
        return self.id


def similarity(parent, child):
    jaccard = parent.num_genes / child.num_genes
    ks_test = ks_2samp(parent.ranks, child.ranks)[1]
    return ks_test * jaccard


def run_legacy(parsed, gene_ranks, *, min_genes, max_level, p_value_threshold, use_fdr):
    """parsed: list of (frozenset[genesets], list[genes]). Returns a comparable structure."""
    bicliques_by_size = {}
    next_id = 0
    for genesets, genes in parsed:
        if len(genes) < min_genes:
            continue
        next_id += 1
        genes_dict = {g: gene_ranks[g] for g in genes if g in gene_ranks}
        bicliques_by_size.setdefault(len(genesets), []).append(
            Biclique(next_id, genesets, genes_dict)
        )

    bicliques = sorted(bicliques_by_size.items(), key=lambda k: k[0])
    if not bicliques:
        return {"nodes": {}, "links": {}, "cut_depth": 0}

    num_bicliques = sum(len(lst) for _, lst in bicliques)

    # find_cut_depth (legacy)
    cut_depth = 0
    if max_level != 0:
        for size, lst in reversed(bicliques[1:]):
            levelcount = sum(b.displayed for b in lst)
            if levelcount > max_level:
                cut_depth = size

    # subset relationships
    p_values = []
    for i in range(1, len(bicliques)):
        for biclique in bicliques[i][1]:
            covered = set()
            for j in range(i - 1, -1, -1):
                for b in bicliques[j][1]:
                    if b.genesets < biclique.genesets:
                        if b not in covered:
                            sim = similarity(biclique, b)
                            biclique.children[b] = sim
                            b.parents[biclique] = sim
                            covered.add(b)
                            p_values.append(sim)
                        covered |= set(b.children)

    # p-value trim
    if p_value_threshold < 0.99999:
        if use_fdr and p_values:
            n = len(p_values)
            pv = np.array(p_values)
            pv.sort()
            fdr_range = np.linspace(p_value_threshold / n, p_value_threshold, n)
            crossings = np.where(pv > fdr_range)[0]
            threshold = fdr_range[crossings[0]] if len(crossings) else p_value_threshold
        else:
            threshold = p_value_threshold
        for _size, lst in bicliques[:-1]:
            for biclique in lst:
                to_remove = [p for p, sim in biclique.parents.items() if sim > threshold]
                for p in to_remove:
                    del biclique.parents[p]
                    del p.children[biclique]

    # trim unconnected / cut by depth
    i = 0
    while i < len(bicliques):
        size, lst = bicliques[i]
        if size <= cut_depth:
            bicliques.pop(i)
            continue
        j = 0
        while j < len(lst):
            b = lst[j]
            if not b.displayed or (not b.parents and not b.children):
                lst.pop(j)
            else:
                j += 1
        if not lst:
            bicliques.pop(i)
        else:
            i += 1

    # comparable structure keyed by gene-set frozenset. Legacy filters edges to cut/
    # undisplayed children at OUTPUT time (if ch.size <= cut_depth or not ch.displayed:
    # continue), so only keep links whose child survived the trim.
    nodes = {}
    for _size, lst in bicliques:
        for b in lst:
            nodes[b.genesets] = sorted(b.genes)
    links = {}
    for _size, lst in bicliques:
        for b in lst:
            for child, score in b.children.items():
                if child.genesets in nodes:
                    links[(b.genesets, child.genesets)] = float(score)
    return {"nodes": nodes, "links": links, "cut_depth": cut_depth, "n": num_bicliques}
