"""Endpoints for running the ported analysis tools.

`GET /tools` lists every registered tool and whether it can run here; `POST /tools/{tool}`
runs one. Seven of the nine run in-process today. MSET and PhenomeMap do not -- they shell
out to compiled TOOLBOX binaries that the API image deliberately does not carry, and reach
them instead through the native worker on AsyncTask. Asking for one returns that
explanation rather than a missing-binary stack trace.

`POST /tools/upset` is kept as well, because its typed response (`UpSetResult`) is what the
Analyze page reads for the plot. The generic endpoint returns the tool's own output
verbatim, which is right for eight tools and a needless reshape for the ninth.

Runs are **synchronous** while tool execution lives in-process. That is deliberate and
temporary -- see `services/tool_runner.py`. The gene-set count is capped for the same
reason. The longer-running tools want the AsyncTask run model (roadmap A4/A5), which
returns a run id rather than a result.

Access is via `optional_full_user`, matching `/genesets/search`: an anonymous caller may
run a tool over gene sets that are publicly readable, and nothing else. The gate lives in
the service layer so it cannot be skipped by a future endpoint.
"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Security, status
from jax.apiutils import Response

from geneweaver.api import dependencies as deps
from geneweaver.api.schemas.auth import UserInternal
from geneweaver.api.schemas.tools import ToolRunRequest, UpSetRequest
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


@router.get("")
def list_tools() -> Response:
    """List every registered tool and whether it can be run through this API.

    Served from the registry rather than a hand-maintained list so the front end cannot
    drift from what is actually installed -- the Analyze page previously offered five of
    the nine tools, which understated the port.
    """
    return Response(object={"tools": tool_service.tool_availability()})


@router.post("/{tool}")
def run_tool(
    tool: Annotated[str, Path(description="Tool name, as listed by GET /tools.")],
    request: Annotated[ToolRunRequest, Body(description="Gene sets and tool options.")],
    user: UserInternal = Security(deps.optional_full_user),
    cursor: deps.Cursor | None = Depends(deps.cursor),
) -> Response:
    """Run one tool over two or more gene sets.

    Responds 403 if any requested gene set is not readable, 404 for an unknown tool, and
    409 for a tool that is registered but cannot run in this process -- with the reason,
    so the caller knows whether to wait for AsyncTask or fix the request.

    Only `UnknownToolError` becomes a 404, not any `LookupError`: an `IndexError` raised
    inside a tool is also a LookupError, and catching the base class reported a bug in the
    tool as a missing tool.
    """
    try:
        result = tool_service.run_tool(
            cursor,
            tool_name=tool,
            geneset_ids=request.geneset_ids,
            user=user,
            parameters=request.parameters,
        )
    except tool_service.UnknownToolError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        # Registered but not runnable here: a conflict with the server's state, not a
        # malformed request, so not a 422.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return Response(object=result)
