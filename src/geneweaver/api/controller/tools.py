"""Endpoints for running the ported analysis tools.

Only UpSet is exposed so far. It is the right first tool: pure Python, no native binary,
and it does not depend on `gene_rank` or `jaccard_distribution_results`, both of which are
empty or zero across local, dev and sqa.

Runs are **synchronous** while tool execution lives in-process. That is deliberate and
temporary -- see `services/tool_runner.py`. Endpoints for the binary-backed and
longer-running tools should not be added on this shape; they need the AsyncTask run model
(roadmap A4/A5), which returns a run id rather than a result.

Access is via `optional_full_user`, matching `/genesets/search`: an anonymous caller may
run a tool over gene sets that are publicly readable, and nothing else. The gate lives in
the service layer so it cannot be skipped by a future endpoint.
"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Security
from jax.apiutils import Response

from geneweaver.api import dependencies as deps
from geneweaver.api.schemas.auth import UserInternal
from geneweaver.api.schemas.tools import UpSetRequest
from geneweaver.api.services import tools as tool_service

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/upset")
def run_upset(
    request: Annotated[UpSetRequest, Body(description="Gene sets to intersect.")],
    user: UserInternal = Security(deps.optional_full_user),
    cursor: deps.Cursor | None = Depends(deps.cursor),
) -> Response:
    """Run UpSet over two or more gene sets.

    Returns the number of genes exclusive to each combination of gene sets -- the data
    behind an UpSet plot. Responds 403 if any requested gene set is not readable.
    """
    result = tool_service.run_upset(
        cursor,
        geneset_ids=request.geneset_ids,
        user=user,
        include_zeros=request.include_zeros,
    )
    return Response(object=result)
