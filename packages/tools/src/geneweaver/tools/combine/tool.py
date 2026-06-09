"""Combine tool, reimplemented on the AbstractTool framework.

Ported faithfully from the legacy Celery worker
``legacy/tools-worker/tools/toolbase.py::combine_genesets`` (the legacy
``Combine.mainexec`` was a no-op; the work was done in the base class).

The legacy code ran three SQL queries inside the task. Here those results are passed in
via CombineInput, so this tool is pure: same matrix-building + homology merge, no DB or
Celery coupling. Celery progress reporting is dropped (execution-framework concern).
"""

from __future__ import annotations

import re
from typing import Any

from geneweaver.tools.framework.abstract import AbstractTool

from .schema import CombineInput, CombineOutput

_WHITESPACE = re.compile("[\t\n]")


def build_matrix(
    geneset_ids: list[int],
    membership_rows: list[list[Any]],
    homology_pairs: list[list[Any]],
    include_homology: bool = True,
) -> dict[int, dict[int, Any]]:
    """Build the gene x gene-set membership matrix, merging homologous genes."""
    matrix: dict[int, dict[int, Any]] = {}
    for row in membership_rows:
        gs_id, gene_id, ode_ref_id = row[0], row[1], row[2]
        if gene_id not in matrix:
            matrix[gene_id] = {}
        matrix[gene_id][0] = ode_ref_id
        matrix[gene_id][gs_id] = 1

    if not (homology_pairs and include_homology):
        return matrix

    homologs: dict[int, dict[int, int]] = {}
    for row in homology_pairs:
        a, b = row[0], row[1]
        homologs.setdefault(a, {})[b] = 1
        homologs.setdefault(b, {})[a] = 1

    # Bucket genes by homolog count, process the most-connected first.
    by_count: dict[int, list[int]] = {}
    for gene, neighbours in homologs.items():
        by_count.setdefault(len(neighbours) + 1, []).append(gene)

    for count in sorted(by_count.keys(), reverse=True):
        for candidate in by_count[count]:
            if candidate not in homologs or candidate not in matrix:
                continue
            row_acc = matrix[candidate]
            added = False
            for g2 in list(homologs[candidate].keys()):
                if g2 not in matrix:
                    continue
                for gs_id in geneset_ids:
                    if matrix[g2].get(gs_id) and not row_acc.get(gs_id):
                        row_acc[gs_id] = 1
                        added = True
                matrix.pop(g2, None)
                homologs.pop(g2, None)
            if added:
                matrix[-candidate] = row_acc
                del matrix[candidate]
    return matrix


class Combine(AbstractTool):
    """Combine multiple gene sets into a single gene x gene-set membership matrix."""

    @property
    def tool_input(self) -> type[CombineInput]:
        """Input schema for the tool."""
        return CombineInput

    @property
    def tool_output(self) -> type[CombineOutput]:
        """Output schema for the tool."""
        return CombineOutput

    def run(self, tool_input: CombineInput) -> CombineOutput:
        """Combine the gene sets, optionally integrating homologous genes."""
        matrix = build_matrix(
            tool_input.geneset_ids,
            tool_input.membership_rows,
            tool_input.homology_pairs,
            tool_input.include_homology,
        )
        gslabels: dict[int, str] = {}
        gsnames: dict[int, str] = {}
        for row in tool_input.label_rows:
            gs_id, gs_name, gs_label = row[0], row[1], row[2]
            gslabels[gs_id] = _WHITESPACE.sub(" ", str(gs_label))
            gsnames[gs_id] = _WHITESPACE.sub(" ", str(gs_name))

        return CombineOutput(
            geneset_ids=tool_input.geneset_ids,
            include_homology=tool_input.include_homology,
            matrix=matrix,
            gslabels=gslabels,
            gsnames=gsnames,
        )
