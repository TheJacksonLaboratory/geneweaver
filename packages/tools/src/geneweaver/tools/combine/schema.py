"""Input/output schemas for the Combine tool."""

from __future__ import annotations

from typing import Any

from geneweaver.tools.framework.schema import ToolInput, ToolOutput
from pydantic import Field


class CombineInput(ToolInput):
    """Input for the Combine tool.

    The three row sets correspond to the legacy ``TOOLSET_SQL`` queries (resolved from
    the GeneWeaver DB by the caller, keeping the tool pure):

    - ``membership_rows`` (data1): ``[gs_id, ode_gene_id, ode_ref_id]``
    - ``homology_pairs``  (data2): ``[ode_gene_id_a, ode_gene_id_b]``
    - ``label_rows``      (data3): ``[gs_id, gs_name, gs_label]``
    """

    geneset_ids: list[int]
    include_homology: bool = True
    membership_rows: list[list[Any]] = Field(default_factory=list)
    homology_pairs: list[list[Any]] = Field(default_factory=list)
    label_rows: list[list[Any]] = Field(default_factory=list)


class CombineOutput(ToolOutput):
    """Combined gene x gene-set membership matrix.

    The legacy tool embedded gene-set labels/names under a special ``'==HEADER=='`` key
    in the matrix; here they are pulled into typed ``gslabels`` / ``gsnames`` fields.
    Matrix keys are ode_gene_ids (negative when homolog-merged); each row maps
    ``0 -> ode_ref_id`` and ``gs_id -> 1`` for membership.
    """

    geneset_ids: list[int]
    include_homology: bool
    matrix: dict[int, dict[int, Any]]
    gslabels: dict[int, str]
    gsnames: dict[int, str]
