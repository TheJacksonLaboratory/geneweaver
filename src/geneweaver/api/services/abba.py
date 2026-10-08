"""ABBA, legacy's gene-centred search, run on AsyncTask like every other tool.

ABBA is a SQL pipeline over the whole gene-set corpus (`geneweaver.tools.abba.search`), not
a computation over input the API hands it. Where AsyncTask is configured it still goes there,
as the signed-in user, through the same `GeneWeaverToolWorkflow`: the tool worker searches
the database from inside the activity, so the run shows in Temporal and is polled by run id
like the others. The API's part is what needs the caller:

- the gate on seed gene sets, which are then expanded to their genes here, so the worker is
  never asked to read a gene set on anyone's behalf;
- the caller's identity, signed (`geneweaver.tools.abba.identity`), so the worker searches
  their private gene sets and a run submitted to AsyncTask directly cannot claim someone
  else's.

Where AsyncTask is not configured, the same search runs here on a pooled connection, for as
long as it takes -- 20 to 60 seconds on dev. At most `ABBA_MAX_CONCURRENT` run at once per
process, so they cannot take the pool from every other request; the next is refused with
`ABBABusy` (503) rather than queued.
"""

import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from geneweaver.db.query import abba as abba_queries
from geneweaver.tools.abba import TOOL_NAME, ABBAInput
from geneweaver.tools.abba.identity import sign
from geneweaver.tools.abba.search import search
from psycopg import Cursor
from psycopg.rows import tuple_row
from pydantic import ValidationError

from geneweaver.api.core.config import settings
from geneweaver.api.schemas.auth import User
from geneweaver.api.schemas.tools import ABBARequest
from geneweaver.api.services.asynctask import AsyncTaskClient
from geneweaver.api.services.geneset import determine_user_id
from geneweaver.api.services.tools import (
    ToolRequestError,
    _check_size,
    _gate_geneset_access,
    _require_user,
    _run_on_asynctask,
    asynctask_client_for,
)

_running = threading.BoundedSemaphore(settings.ABBA_MAX_CONCURRENT)


class ABBABusy(Exception):
    """Too many in-process searches are running; the caller should retry (503)."""


@dataclass
class PreparedABBA:
    """A search with the caller's database reads done: gate, seed expansion, identity."""

    shaped: dict[str, Any]
    tool_input: ABBAInput
    user_id: int
    asynctask: AsyncTaskClient | None


def seed_genes(cursor: Cursor, request: ABBARequest) -> list[str]:
    """The typed seed genes, then the genes of the seed gene sets, without repeats.

    The gene sets must already have been gated. Read on a tuple-row cursor because the
    query is the pipeline's own, which reads by position.
    """
    genes = list(request.genes)
    if request.geneset_ids:
        with cursor.connection.cursor(row_factory=tuple_row) as rows:
            rows.execute(*abba_queries.ref_ids_for_genesets(request.geneset_ids))
            genes.extend(str(row[0]) for row in rows.fetchall())
    return genes


def prepare_abba(cursor: Cursor, request: ABBARequest, user: User | None) -> PreparedABBA:
    """Gate the seed gene sets and build the search's input.

    :raises SignInRequired: If the caller is anonymous.
    :raises UnauthorizedException: If a seed gene set is not readable by the caller.
    :raises ToolRequestError: If the input is refused, e.g. too large to submit.
    """
    _require_user(user)
    _gate_geneset_access(cursor, user, request.geneset_ids)
    try:
        tool_input = ABBAInput(
            genes=seed_genes(cursor, request),
            **request.model_dump(exclude={"genes", "geneset_ids"}),
        )
    except ValidationError as error:
        raise ToolRequestError(f"Invalid input for abba: {error}") from error
    return PreparedABBA(
        shaped={
            "tool": TOOL_NAME,
            "geneset_ids": request.geneset_ids,
            # ABBA's seed is genes, not gene sets compared, so there are no per-set counts.
            "gene_counts": {},
            "caveat": None,
        },
        tool_input=tool_input,
        user_id=determine_user_id(user),
        asynctask=asynctask_client_for(user),
    )


def envelope_for(prepared: PreparedABBA) -> dict[str, Any]:
    """The AsyncTask request: the input, and beside it who the search is for, signed."""
    return {
        "tool": TOOL_NAME,
        "input": prepared.tool_input.model_dump(mode="json"),
        "identity": sign(prepared.user_id, settings.DB_PASSWORD),
    }


def run_abba(
    open_cursor: Callable[[], AbstractContextManager[Cursor]],
    request: ABBARequest,
    user: User | None,
) -> dict[str, Any]:
    """Gate, run and return one ABBA search, in the shape every tool run returns.

    :return: ``{tool, geneset_ids, gene_counts, caveat, executed_by, run_id, result}``.
    :raises SignInRequired: If the caller is anonymous.
    :raises UnauthorizedException: If a seed gene set is not readable by the caller.
    :raises ToolRequestError: If the input is refused.
    :raises ToolRunPending: If the AsyncTask run outlasts the wait; poll it by run id.
    :raises ToolRunFailed: If the AsyncTask run fails.
    :raises ABBABusy: If, in-process, `ABBA_MAX_CONCURRENT` searches are already running.
    """
    # Before the cursor: an anonymous request is refused without leasing a connection.
    _require_user(user)
    if asynctask_client_for(user) is not None:
        # The connection goes back to the pool before the wait on AsyncTask.
        with open_cursor() as cursor:
            prepared = prepare_abba(cursor, request, user)
        envelope = envelope_for(prepared)
        _check_size(envelope)
        label = f"{TOOL_NAME}: " + ", ".join(prepared.tool_input.genes[:5])
        return {
            **prepared.shaped,
            "executed_by": "asynctask",
            **_run_on_asynctask(prepared.asynctask, envelope, prepared.shaped, label=label),
        }

    if not _running.acquire(blocking=False):
        raise ABBABusy(
            f"{settings.ABBA_MAX_CONCURRENT} ABBA searches are already running; "
            "try again in a minute."
        )
    try:
        with open_cursor() as cursor:
            prepared = prepare_abba(cursor, request, user)
            output = search(
                cursor.connection,
                prepared.tool_input,
                prepared.user_id,
                statement_timeout_seconds=settings.ABBA_STATEMENT_TIMEOUT_SECONDS,
            )
    finally:
        _running.release()
    return {
        **prepared.shaped,
        "executed_by": "in_process",
        "run_id": None,
        "result": output.model_dump(mode="json"),
    }
