"""A user's tool runs on AsyncTask: list, read, delete, rerun and expire them (G3-801).

AsyncTask owns run state and v3 keeps no run table (roadmap §4 guardrail 1), so everything
here is done through AsyncTask's API **as the user**, and AsyncTask's owner check is what
keeps one user from another's runs. What AsyncTask guarantees was read from its code
(asynctask 5f2acea, the build dev runs), not assumed -- G3-736 and G3-739 showed its
guarantees cannot be taken on trust:

- ``GET /runs`` lists the caller's runs of **every** plugin, so a GeneWeaver run is told
  apart by its workflow id, ``ats:GeneWeaverTools:<uuid>``. Its ``?workflow_id=`` filter
  returns a run *without* checking its owner, and is never used.
- A run carries no tool name or request; the request is kept as its input's description
  (`run_record`) and read back through ``GET /inputs``.
- ``DELETE /runs/{id}`` refuses a run that still has a result, and does not stop a running
  workflow; so a run is cancelled if running, its result deleted, then the run.
- A failed run is only a status: AsyncTask stores no reason, and sets no workflow timeout,
  so a run whose workflow never starts stays RUNNING forever (G3-739). Runs are therefore
  reported with what is known -- the status, and *stalled* past
  ``TOOL_RUN_STALLED_AFTER_MINUTES`` -- rather than a reason the API cannot have.
- AsyncTask keeps runs forever. ``TOOL_RUN_RETENTION_DAYS`` is applied per user, when they
  list their runs, since only a run's owner may delete it.

Reading a result re-checks access (G3-736): the caller must still be able to read the run's
input gene sets, and gene sets named in an ABBA or Similar gene sets result that the caller
can no longer read are withheld.
"""

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from typing import Any

from geneweaver.db import geneset as db_geneset
from psycopg import Cursor
from pydantic import ValidationError

from geneweaver.api.core.config import settings
from geneweaver.api.schemas.auth import User
from geneweaver.api.services.asynctask import (
    COMPLETED,
    RUNNING,
    TASK_TYPE,
    AsyncTaskClient,
    AsyncTaskError,
    status_name,
)
from geneweaver.api.services.geneset import determine_user_id
from geneweaver.api.services.run_record import RunRecord
from geneweaver.api.services.tools import (
    SignInRequired,
    ToolRequestError,
    ToolRunPending,
    _gate_geneset_access,
    asynctask_client_for,
    asynctask_configured,
    execute_tool_run,
    precheck_run,
    prepare_tool_run,
)

logger = logging.getLogger(__name__)

#: AsyncTask names a run's workflow ``ats:<plugin>:<uuid>`` (its TemporalAdapter.submit).
WORKFLOW_PREFIX = f"ats:{TASK_TYPE}:"

#: Tools whose result lists gene sets beyond the run's input, each with a ``gs_id``.
RESULT_GENESETS_TOOLS = frozenset({"abba", "similar_genesets"})

OpenCursor = Callable[[], AbstractContextManager[Cursor]]


class RunNotFound(Exception):
    """No GeneWeaver tool run with that id belongs to the caller (404)."""


class RunsNotStored(RunNotFound):
    """This environment does not send runs to AsyncTask, so there are none to manage (404)."""


class RunNotRerunnable(Exception):
    """The run kept no record of its request, so it cannot be submitted again (409)."""


class RunNotReadable(Exception):
    """The run's gene sets cannot be found, so access to its result cannot be checked (409)."""


def is_geneweaver_run(workflow_id: object) -> bool:
    """Whether a run is one of ours, not another AsyncTask plugin's."""
    return isinstance(workflow_id, str) and workflow_id.startswith(WORKFLOW_PREFIX)


def client_for(user: User | None) -> AsyncTaskClient:
    """The caller's AsyncTask client.

    :raises RunsNotStored: If this environment does not send runs to AsyncTask.
    :raises SignInRequired: If the caller is anonymous.
    """
    if not asynctask_configured():
        raise RunsNotStored("Tool runs are not sent to AsyncTask in this environment.")
    client = asynctask_client_for(user)
    if client is None:
        raise SignInRequired("Sign in to see your tool runs.")
    return client


def _started(value: object) -> datetime | None:
    """AsyncTask's ``init_time`` as an aware datetime; naive values are UTC."""
    if not isinstance(value, str):
        return None
    try:
        started = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return started if started.tzinfo else started.replace(tzinfo=timezone.utc)


def run_problem(status: str, init_time: object, now: datetime) -> tuple[bool, str | None]:
    """Whether a run is stalled, and what can be said about one that did not complete.

    Only what AsyncTask knows: it records no reason for a failure (G3-739).

    :return: ``(stalled, problem)``; ``problem`` is None for a healthy or completed run.
    """
    if status == RUNNING:
        started = _started(init_time)
        limit = timedelta(minutes=settings.TOOL_RUN_STALLED_AFTER_MINUTES)
        if started is not None and now - started > limit:
            return True, (
                f"Still running after {settings.TOOL_RUN_STALLED_AFTER_MINUTES} minutes. A "
                "tool run takes at most about 30 minutes once a worker picks it up, so this "
                "one has most likely never started: the analysis service is down or not set "
                "up for GeneWeaver tools. It will not finish on its own; delete it and run it "
                "again later."
            )
        return False, None
    problems = {
        "failed": (
            "The run failed. The analysis service records only that it failed, not why; "
            "check the request, or run it again."
        ),
        "timed_out": "The run ran out of time.",
        "cancelled": "The run was cancelled.",
        "terminated": "The run was stopped by an administrator.",
    }
    if status == COMPLETED:
        return False, None
    return False, problems.get(status, f"The run ended {status}.")


def _summary(run: dict[str, Any], inputs: dict[int, dict[str, Any]], now: datetime) -> dict:
    """One run for the listing: what was run, on what, and how it went."""
    status = status_name(run.get("status"))
    stalled, problem = run_problem(status, run.get("init_time"), now)
    run_input = inputs.get(run.get("input_id"), {})
    record = RunRecord.from_description(run_input.get("description"))
    return {
        "run_id": run["id"],
        "tool": record.tool if record else None,
        "name": run_input.get("name"),
        "geneset_ids": record.geneset_ids if record else None,
        "status": status,
        "stalled": stalled,
        "problem": problem,
        "created": run.get("init_time"),
        "can_rerun": record is not None,
    }


def _our_runs(client: AsyncTaskClient) -> list[dict[str, Any]]:
    """The caller's GeneWeaver tool runs, each with an integer id."""
    return [
        run
        for run in client.list_runs()
        if is_geneweaver_run(run.get("workflow_id"))
        and isinstance(run.get("id"), int)
        and not isinstance(run.get("id"), bool)
    ]


def _remove(client: AsyncTaskClient, run_id: int, status: str) -> None:
    """Delete a run as AsyncTask requires: stop it if running, drop its result, then it.

    A cancel that AsyncTask refuses with 400 means the run stopped meanwhile; that is fine.
    """
    if status == RUNNING:
        try:
            client.cancel(run_id)
        except AsyncTaskError as error:
            if error.status_code != 400:
                raise
    result_id = client.result_id(run_id)
    if result_id is not None:
        client.delete_result(result_id)
    client.delete_run(run_id)


def _older_than(runs: list[dict[str, Any]], cutoff: datetime) -> list[dict[str, Any]]:
    """Runs started before ``cutoff``; a run with no start time is never old."""
    old = []
    for run in runs:
        started = _started(run.get("init_time"))
        if started is not None and started < cutoff:
            old.append(run)
    return old


def _delete_all(client: AsyncTaskClient, runs: list[dict[str, Any]], strict: bool) -> set[int]:
    """Delete these runs; the ids deleted.

    :param strict: Raise the first failure (a request to delete), or log it and go on
        (expiry while listing, which must not cost the user their list).
    """
    deleted = set()
    for run in runs:
        try:
            _remove(client, run["id"], status_name(run.get("status")))
        except AsyncTaskError as error:
            if strict:
                raise
            logger.warning(
                "Could not expire tool run %s (AsyncTask status %s).", run["id"], error.status_code
            )
            continue
        deleted.add(run["id"])
    return deleted


def list_runs(
    user: User | None, limit: int = 25, offset: int = 0, now: datetime | None = None
) -> dict[str, Any]:
    """The caller's tool runs, newest first, one page of them.

    Runs older than ``TOOL_RUN_RETENTION_DAYS`` are deleted first, as the caller.

    :return: ``{runs, total, expired, retention_days}``.
    """
    now = now or datetime.now(timezone.utc)
    client = client_for(user)
    runs = _our_runs(client)
    expired: set[int] = set()
    if settings.TOOL_RUN_RETENTION_DAYS > 0:
        cutoff = now - timedelta(days=settings.TOOL_RUN_RETENTION_DAYS)
        expired = _delete_all(client, _older_than(runs, cutoff), strict=False)
    runs = [run for run in runs if run["id"] not in expired]
    inputs = {
        item["id"]: item
        for item in client.list_inputs()
        if isinstance(item.get("id"), int) and not isinstance(item.get("id"), bool)
    }

    def newest_first(run: dict[str, Any]) -> tuple:
        started = _started(run.get("init_time"))
        return (started is not None, started or now, run["id"])

    runs.sort(key=newest_first, reverse=True)
    page = runs[offset : offset + limit]
    return {
        "runs": [_summary(run, inputs, now) for run in page],
        "total": len(runs),
        "expired": len(expired),
        "retention_days": settings.TOOL_RUN_RETENTION_DAYS,
    }


def _our_run(client: AsyncTaskClient, run_id: int):
    """The run's status, refusing one that is not a GeneWeaver tool run.

    :raises RunNotFound: For another plugin's run.
    """
    state = client.get_status(run_id)
    if not is_geneweaver_run(state.workflow_id):
        raise RunNotFound(f"Run {run_id} is not a GeneWeaver tool run.")
    return state


def delete_run(user: User | None, run_id: int) -> None:
    """Delete one of the caller's runs, stopping it first if it is still running.

    :raises RunNotFound: If it is not a GeneWeaver tool run.
    """
    client = client_for(user)
    state = _our_run(client, run_id)
    _remove(client, run_id, state.status)


def delete_runs_older_than(user: User | None, days: int, now: datetime | None = None) -> int:
    """Delete every run of the caller's started more than ``days`` days ago; how many."""
    now = now or datetime.now(timezone.utc)
    client = client_for(user)
    old = _older_than(_our_runs(client), now - timedelta(days=days))
    return len(_delete_all(client, old, strict=True))


def _unwrap(values: object) -> dict[str, Any]:
    """AsyncTask may store an input's values as ``{"values": {...}}``; the envelope inside."""
    if isinstance(values, dict) and isinstance(values.get("values"), dict):
        return values["values"]
    return values if isinstance(values, dict) else {}


def _from_envelope(values: object) -> tuple[str | None, list[int] | None]:
    """The tool and gene sets a run's envelope shows -- the input as submitted.

    Unlike the record, which is the input's *description* and so editable by its owner
    (AsyncTask's ``PATCH /inputs/{id}``), the envelope cannot be changed after submission,
    so it is what the tool and, where it carries them, the gene sets are taken from. Where
    each tool keeps its gene sets: ``input.geneset_ids`` (most, as strings), ``group_a`` and
    ``group_b`` (Triclique), the keys of ``gene_sets`` (PhenomeMap), ``universe.geneset_ids``
    (MSET), ``input.geneset_id`` (Similar gene sets). ABBA's seed gene sets are expanded to
    genes before submission, so it shows none.

    :return: ``(tool, gene sets)``; gene sets None where the envelope shows none to check.
    """
    envelope = _unwrap(values)
    tool = envelope.get("tool") if isinstance(envelope.get("tool"), str) else None
    tool_input = envelope.get("input") if isinstance(envelope.get("input"), dict) else {}
    universe = envelope.get("universe") if isinstance(envelope.get("universe"), dict) else {}
    found: list[Any] = []
    shown = False
    for value in (
        tool_input.get("geneset_ids"),
        tool_input.get("group_a"),
        tool_input.get("group_b"),
        universe.get("geneset_ids"),
    ):
        if isinstance(value, list):
            found += value
            shown = True
    if isinstance(tool_input.get("gene_sets"), dict):
        found += list(tool_input["gene_sets"])
        shown = True
    if isinstance(tool_input.get("geneset_id"), int):
        found.append(tool_input["geneset_id"])
        shown = True
    if not shown:
        return tool, [] if tool == "abba" else None
    try:
        return tool, sorted({int(value) for value in found})
    except (TypeError, ValueError):
        return tool, None


def _withhold_unreadable(
    cursor: Cursor, user: User | None, tool: str | None, result: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    """Drop gene sets from an ABBA or Similar gene sets result the caller can no longer read.

    Those results name gene sets beyond the input -- the ones the caller could read when it
    ran. Counts derived from them (ABBA's per-gene occurrences) are left as they ran.

    :return: The result, and how many gene sets were withheld.
    """
    rows = result.get("genesets")
    if tool not in RESULT_GENESETS_TOOLS or not isinstance(rows, list):
        return result, 0
    ids = [
        row["gs_id"] for row in rows if isinstance(row, dict) and isinstance(row.get("gs_id"), int)
    ]
    readable = db_geneset.readable_ids(cursor, determine_user_id(user), ids)
    kept = [row for row in rows if not isinstance(row, dict) or row.get("gs_id") in readable]
    return {**result, "genesets": kept}, len(rows) - len(kept)


def _consistent_record(run_input: dict[str, Any]) -> RunRecord | None:
    """The run's record, unless its tool disagrees with the envelope's.

    The record is an editable description; one claiming another tool than the run's own
    envelope (an edited one) is ignored rather than trusted.
    """
    record = RunRecord.from_description(run_input.get("description"))
    tool, _ = _from_envelope(run_input.get("values"))
    if record is not None and tool is not None and record.tool != tool:
        return None
    return record


def read_run(
    open_cursor: OpenCursor, user: User | None, run_id: int, now: datetime | None = None
) -> dict[str, Any]:
    """A run's status, and its result once complete and still readable by the caller.

    :raises RunNotFound: If it is not a GeneWeaver tool run.
    :raises UnauthorizedException: If the caller can no longer read one of its gene sets.
    :raises RunNotReadable: If a completed run's gene sets cannot be found to check.
    """
    now = now or datetime.now(timezone.utc)
    client = client_for(user)
    state = _our_run(client, run_id)
    run_input = client.get_run_input(run_id)
    record = _consistent_record(run_input)
    tool, shown = _from_envelope(run_input.get("values"))
    tool = tool or (record.tool if record else None)
    # Every gene set either names: the envelope's cannot be edited, the record's (ABBA's seed
    # gene sets, which its envelope no longer shows) can, but only by the run's owner.
    if shown is None and record is None:
        geneset_ids = None
    else:
        geneset_ids = sorted(set(shown or []) | set(record.geneset_ids if record else []))
    stalled, problem = run_problem(state.status, state.init_time, now)
    body: dict[str, Any] = {
        "run_id": state.run_id,
        "tool": tool,
        "geneset_ids": geneset_ids,
        "status": state.status,
        "stalled": stalled,
        "problem": problem,
        "workflow_id": state.workflow_id,
        "created": state.init_time,
        "can_rerun": record is not None,
        "withheld_genesets": 0,
        "result": None,
    }
    if state.status != COMPLETED:
        return body
    if geneset_ids is None:
        raise RunNotReadable(
            f"Run {run_id} was submitted before runs recorded their gene sets, so whether "
            "you may still read them cannot be checked. Run the analysis again."
        )
    # Fetched before the cursor is leased: no connection is held across a call to AsyncTask.
    result = client.get_result(run_id)
    with open_cursor() as cursor:
        _gate_geneset_access(cursor, user, geneset_ids)
        result, withheld = _withhold_unreadable(cursor, user, tool, result)
    return {**body, "result": result, "withheld_genesets": withheld}


def rerun(open_cursor: OpenCursor, user: User | None, run_id: int) -> dict[str, Any]:
    """Submit a run's request again, as a new run, through the same gate as the first.

    The gene sets are checked and resolved again -- the caller's access, and the gene sets'
    contents, may have changed -- and ABBA and Similar gene sets are signed again, as their
    signed identity expires. Answers as the run endpoints do.

    :raises RunNotFound: If it is not a GeneWeaver tool run.
    :raises RunNotRerunnable: If the run kept no record of its request.
    :raises ToolRequestError: If the recorded request no longer validates.

    A registered tool's rerun answers in the generic shape, as ``POST /tools/{tool}`` does,
    UpSet's included (not ``POST /tools/upset``'s typed `UpSetResult`).
    """
    from geneweaver.api.schemas.tools import ABBARequest, SimilarGenesetsRequest, ToolRunRequest
    from geneweaver.api.services import abba as abba_service
    from geneweaver.api.services import similar_genesets as similar_service

    client = client_for(user)
    _our_run(client, run_id)
    record = _consistent_record(client.get_run_input(run_id))
    if record is None:
        raise RunNotRerunnable(
            f"Run {run_id} was submitted before runs recorded their request, so it cannot be "
            "run again from here. Start it again from the analysis page."
        )
    try:
        if record.tool == "abba":
            output = abba_service.run_abba(
                open_cursor, ABBARequest.model_validate(record.request), user
            )
        elif record.tool == "similar_genesets":
            output = similar_service.run_similar_genesets(
                open_cursor, SimilarGenesetsRequest.model_validate(record.request), user
            )
        else:
            # The endpoint's own request checks (2 to 20 distinct gene sets), as a new run gets.
            request = ToolRunRequest.model_validate(record.request)
            precheck_run(record.tool, user)
            with open_cursor() as cursor:
                prepared = prepare_tool_run(
                    cursor,
                    tool_name=record.tool,
                    geneset_ids=list(request.geneset_ids),
                    user=user,
                    parameters=dict(request.parameters),
                )
            output = execute_tool_run(prepared)
    except ValidationError as error:
        raise ToolRequestError(f"Run {run_id}'s request no longer validates: {error}") from error
    except ToolRunPending as pending:
        pending.body["rerun_of"] = run_id
        raise
    return {**output, "rerun_of": run_id}
