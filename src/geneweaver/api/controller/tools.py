"""Endpoints for running the ported analysis tools.

`GET /tools` lists every registered tool and whether it can run here; `POST /tools/{tool}`
runs one. Seven of the nine run in-process today. MSET and PhenomeMap do not -- they shell
out to compiled TOOLBOX binaries that the API image deliberately does not carry, and reach
them instead through the native worker on AsyncTask. Asking for one returns that
explanation rather than a missing-binary stack trace.

`POST /tools/upset` is kept as well, because its typed response (`UpSetResult`) is what the
Analyze page reads for the plot. The generic endpoint returns the tool's own output
verbatim, which is right for eight tools and a needless reshape for the ninth.

Where AsyncTask is configured (`ASYNCTASK_API_URL`), a signed-in caller's run goes there,
including MSET and PhenomeMap. `POST /tools/{tool}` waits up to `ASYNCTASK_WAIT_SECONDS`
and returns the result as before; a run still going at that point is answered **202** with
its `run_id`, which `GET /tools/runs/{run_id}` polls. Anonymous callers, and every caller
where AsyncTask is not configured, run in-process and synchronously as before.

Access is via `optional_full_user`, matching `/genesets/search`: an anonymous caller may
run a tool over gene sets that are publicly readable, and nothing else. The gate lives in
the service layer so it cannot be skipped by a future endpoint.
"""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Security, status
from fastapi import Response as HTTPResponse
from jax.apiutils import Response

from geneweaver.api import dependencies as deps
from geneweaver.api.schemas.auth import UserInternal
from geneweaver.api.schemas.tools import ToolRunRequest, UpSetRequest
from geneweaver.api.services import tools as tool_service
from geneweaver.api.services.asynctask import AsyncTaskError

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/upset")
def run_upset(
    request: Annotated[UpSetRequest, Body(description="Gene sets to intersect.")],
    http_response: HTTPResponse,
    user: UserInternal = Security(deps.optional_full_user),
    cursor: deps.Cursor | None = Depends(deps.cursor),
) -> Response:
    """Run UpSet over two or more gene sets.

    Returns the number of genes exclusive to each combination of gene sets -- the data
    behind an UpSet plot. Responds 403 if any requested gene set is not readable; the
    AsyncTask outcomes are as for `POST /tools/{tool}`.
    """
    return _run_and_map(
        http_response,
        lambda: tool_service.run_upset(
            cursor,
            geneset_ids=request.geneset_ids,
            user=user,
            include_zeros=request.include_zeros,
        ),
    )


@router.get("")
def list_tools() -> Response:
    """List every registered tool and whether it can be run through this API.

    Served from the registry rather than a hand-maintained list so the front end cannot
    drift from what is actually installed -- the Analyze page previously offered five of
    the nine tools, which understated the port.
    """
    return Response(object={"tools": tool_service.tool_availability()})


def _asynctask_http_error(error: AsyncTaskError) -> HTTPException:
    """Pass AsyncTask's ownership and not-found answers through; anything else is a 502.

    A 403 from AsyncTask means the run belongs to someone else, and must stay a 403 here --
    reporting it as an outage would be wrong, and reporting it as a 404 would hide that the
    ownership check is AsyncTask's.
    """
    if error.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND):
        return HTTPException(status_code=error.status_code, detail=str(error))
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error))


def _run_and_map(http_response: HTTPResponse, run: Callable[[], Any]) -> Response:
    """Run a tool and translate each way it can end into its HTTP status.

    Shared by both run endpoints so `/tools/upset` -- the Analyze page's default -- cannot
    drift from `/tools/{tool}` in how an AsyncTask outcome is reported.
    """
    try:
        return Response(object=run())
    except tool_service.UnknownToolError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except tool_service.SignInRequired as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    except tool_service.ToolRequestError as error:
        # A literal: Starlette renamed the 422 constant, and the old name now warns while
        # the new one is missing from releases `fastapi>=0.115.5` still allows.
        raise HTTPException(status_code=422, detail=str(error)) from error
    except tool_service.ToolRunPending as pending:
        http_response.status_code = status.HTTP_202_ACCEPTED
        return Response(object=pending.body)
    except tool_service.ToolRunFailed as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    except AsyncTaskError as error:
        raise _asynctask_http_error(error) from error
    except ValueError as error:
        # Registered but not runnable here: a conflict with the server's state, not a
        # malformed request, so not a 422.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/runs/{run_id}")
def get_tool_run(
    run_id: Annotated[int, Path(description="A run id returned by POST /tools/{tool}.")],
    user: UserInternal = Security(deps.optional_full_user),
) -> Response:
    """Poll a tool run submitted to AsyncTask.

    `status` is one of running, completed, failed, cancelled, terminated or timed_out;
    `result` is the tool's output once completed. Only the run's owner may read it.
    """
    try:
        return Response(object=tool_service.get_tool_run(run_id, user))
    except tool_service.SignInRequired as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AsyncTaskError as error:
        raise _asynctask_http_error(error) from error


@router.post("/{tool}")
def run_tool(
    tool: Annotated[str, Path(description="Tool name, as listed by GET /tools.")],
    request: Annotated[ToolRunRequest, Body(description="Gene sets and tool options.")],
    http_response: HTTPResponse,
    user: UserInternal = Security(deps.optional_full_user),
    cursor: deps.Cursor | None = Depends(deps.cursor),
) -> Response:
    """Run one tool over two or more gene sets.

    Responds 403 if any requested gene set is not readable, 404 for an unknown tool, and
    409 for a tool that is registered but cannot run in this environment -- with the reason,
    so the caller knows whether to wait for a deployment or fix the request. 401 if the tool
    runs only on AsyncTask and the caller is not signed in; 422 if the request does not suit
    the tool; 202 with a `run_id` if an AsyncTask run is still going after the wait; 502 if
    AsyncTask fails the run or cannot be reached.

    Only `UnknownToolError` becomes a 404, not any `LookupError`: an `IndexError` raised
    inside a tool is also a LookupError, and catching the base class reported a bug in the
    tool as a missing tool.
    """
    return _run_and_map(
        http_response,
        lambda: tool_service.run_tool(
            cursor,
            tool_name=tool,
            geneset_ids=request.geneset_ids,
            user=user,
            parameters=request.parameters,
        ),
    )
