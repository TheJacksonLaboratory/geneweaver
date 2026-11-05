"""Similar gene sets, legacy's "Find Similar GeneSets", run on AsyncTask like every tool.

A database search, like ABBA (`services/abba.py`), and wired the same way. Where AsyncTask is
configured it goes there as the signed-in user, and the tool worker searches the database
from inside the activity. The run shows in Temporal and is polled by run id, at
`GET /tools/runs/{run_id}`. The API's part is what needs the caller:

- the gate on the viewed gene set, so no one learns what a gene set they cannot read is
  like;
- the caller's identity, signed (`geneweaver.tools.abba.identity`), so the worker lists their
  private gene sets and a run submitted to AsyncTask directly cannot claim someone else's.

It takes about two minutes on dev, legacy's own cost: every gene of every gene set sharing a
gene with the viewed one is read. Legacy then wrote the result into ``geneset_jaccard``; this
never writes (see `geneweaver.db.query.similar_genesets`).

Where AsyncTask is not configured, the same search runs here on a pooled connection, at most
`SIMILAR_GENESETS_MAX_CONCURRENT` at once per process; the next is refused with
`SimilarGenesetsBusy` (503) rather than queued.
"""

import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from geneweaver.tools.abba.identity import sign
from geneweaver.tools.similar_genesets import TOOL_NAME, SimilarGenesetsInput
from geneweaver.tools.similar_genesets.search import search
from psycopg import Cursor

from geneweaver.api.core.config import settings
from geneweaver.api.schemas.auth import User
from geneweaver.api.services.asynctask import AsyncTaskClient
from geneweaver.api.services.geneset import determine_user_id
from geneweaver.api.services.tools import (
    _check_size,
    _gate_geneset_access,
    _require_user,
    _run_on_asynctask,
    asynctask_client_for,
)

#: In-process searches at once. One: each reads most of ``geneset_value``.
SIMILAR_GENESETS_MAX_CONCURRENT = 1

_running = threading.BoundedSemaphore(SIMILAR_GENESETS_MAX_CONCURRENT)


class SimilarGenesetsBusy(Exception):
    """A search is already running in this process; the caller should retry (503)."""


@dataclass
class PreparedSimilar:
    """A search with the caller's database reads done: the gate and the identity."""

    shaped: dict[str, Any]
    tool_input: SimilarGenesetsInput
    user_id: int
    asynctask: AsyncTaskClient | None


def prepare(cursor: Cursor, request: SimilarGenesetsInput, user: User | None) -> PreparedSimilar:
    """Gate the viewed gene set.

    :raises SignInRequired: If the caller is anonymous.
    :raises UnauthorizedException: If the caller may not read the gene set.
    """
    _require_user(user)
    _gate_geneset_access(cursor, user, [request.geneset_id])
    return PreparedSimilar(
        shaped={
            "tool": TOOL_NAME,
            "geneset_ids": [request.geneset_id],
            "gene_counts": {},
            "caveat": None,
            "thresholds": request.threshold_choice(),
        },
        tool_input=request,
        user_id=determine_user_id(user),
        asynctask=asynctask_client_for(user),
    )


def envelope_for(prepared: PreparedSimilar) -> dict[str, Any]:
    """The AsyncTask request: the input, and beside it who the search is for, signed."""
    return {
        "tool": TOOL_NAME,
        "input": prepared.tool_input.model_dump(mode="json"),
        "identity": sign(prepared.user_id, settings.DB_PASSWORD),
    }


def run_similar_genesets(
    open_cursor: Callable[[], AbstractContextManager[Cursor]],
    request: SimilarGenesetsInput,
    user: User | None,
) -> dict[str, Any]:
    """Gate, run and return one search, in the shape every tool run returns.

    :return: ``{tool, geneset_ids, gene_counts, caveat, thresholds, executed_by, run_id,
        result}``.
    :raises SignInRequired: If the caller is anonymous.
    :raises UnauthorizedException: If the caller may not read the gene set.
    :raises ToolRunPending: If the AsyncTask run outlasts the wait; poll it by run id.
    :raises ToolRunFailed: If the AsyncTask run fails.
    :raises SimilarGenesetsBusy: If, in-process, a search is already running.
    """
    _require_user(user)
    if asynctask_client_for(user) is not None:
        # The connection goes back to the pool before the wait on AsyncTask.
        with open_cursor() as cursor:
            prepared = prepare(cursor, request, user)
        envelope = envelope_for(prepared)
        _check_size(envelope)
        return {
            **prepared.shaped,
            "executed_by": "asynctask",
            **_run_on_asynctask(
                prepared.asynctask,
                envelope,
                prepared.shaped,
                label=f"{TOOL_NAME}: GS{request.geneset_id}",
            ),
        }

    if not _running.acquire(blocking=False):
        raise SimilarGenesetsBusy(
            "A similar gene sets search is already running; try again in a few minutes."
        )
    try:
        with open_cursor() as cursor:
            prepared = prepare(cursor, request, user)
            output = search(cursor.connection, prepared.tool_input, prepared.user_id)
    finally:
        _running.release()
    return {
        **prepared.shaped,
        "executed_by": "in_process",
        "run_id": None,
        "result": output.model_dump(mode="json"),
    }
