"""A user's tool runs on AsyncTask: list, read, delete, rerun, expire (G3-801).

The fake below answers as AsyncTask's API does at 5f2acea -- runs of every plugin under
``GET /runs``, descriptions under ``GET /inputs``, a run's input under its id -- and records
every call, so the order AsyncTask requires for a delete can be checked.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from geneweaver.api.core.exceptions import UnauthorizedException
from geneweaver.api.services import tool_runs as service
from geneweaver.api.services.asynctask import AsyncTaskError, RunState
from geneweaver.api.services.run_record import RunRecord
from geneweaver.api.services.tools import SignInRequired, ToolRequestError, ToolRunPending

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
OURS = "ats:GeneWeaverTools:"
STATUS = {"running": 1, "completed": 2, "failed": 3}


def _at(**ago) -> str:
    return (NOW - timedelta(**ago)).isoformat()


def _record(tool="upset", geneset_ids=(1, 2), **request) -> str:
    request = request or {"geneset_ids": list(geneset_ids), "parameters": {}}
    return RunRecord(tool=tool, geneset_ids=list(geneset_ids), request=request).to_description()


class _FakeAsyncTask:
    """AsyncTask's run API for one user, in memory."""

    def __init__(self) -> None:
        self.runs: dict[int, dict] = {}
        self.inputs: dict[int, dict] = {}
        self.results: dict[int, dict] = {}  # run id -> {"id", "values"}
        self.calls: list[tuple] = []
        self.cancel_error: AsyncTaskError | None = None
        self.delete_error: AsyncTaskError | None = None

    def add(
        self,
        run_id: int,
        status: str = "completed",
        started: str | None = None,
        description: str | None = None,
        values: dict | None = None,
        workflow: str = OURS,
        result: dict | None = None,
    ) -> None:
        self.runs[run_id] = {
            "id": run_id,
            "input_id": 100 + run_id,
            "workflow_id": f"{workflow}{run_id}",
            "status": STATUS.get(status, status),
            "init_time": started or _at(minutes=5),
        }
        self.inputs[100 + run_id] = {
            "id": 100 + run_id,
            "name": f"run {run_id}",
            "description": description,
            "values": values or {"tool": "upset", "input": {}},
        }
        if status == "completed":
            self.results[run_id] = {"id": 900 + run_id, "values": result or {"ok": run_id}}

    def _state(self, run_id: int) -> RunState:
        if run_id not in self.runs:
            raise AsyncTaskError("Run not found.", status_code=404)
        run = self.runs[run_id]
        return RunState(
            run_id=run_id,
            workflow_id=run["workflow_id"],
            status={1: "running", 2: "completed", 3: "failed"}[run["status"]],
            init_time=run["init_time"],
        )

    def list_runs(self):
        self.calls.append(("list_runs",))
        return list(self.runs.values())

    def list_inputs(self):
        self.calls.append(("list_inputs",))
        return [{k: v for k, v in i.items() if k != "values"} for i in self.inputs.values()]

    def get_status(self, run_id):
        self.calls.append(("get_status", run_id))
        return self._state(run_id)

    def get_run_input(self, run_id):
        self.calls.append(("get_run_input", run_id))
        return self.inputs[self.runs[run_id]["input_id"]]

    def get_result(self, run_id, timeout=None):
        self.calls.append(("get_result", run_id))
        return self.results[run_id]["values"]

    def cancel(self, run_id):
        self.calls.append(("cancel", run_id))
        if self.cancel_error:
            raise self.cancel_error
        self.runs[run_id]["status"] = 4

    def result_id(self, run_id):
        self.calls.append(("result_id", run_id))
        result = self.results.get(run_id)
        return result["id"] if result else None

    def delete_result(self, result_id):
        self.calls.append(("delete_result", result_id))
        self.results = {k: v for k, v in self.results.items() if v["id"] != result_id}

    def delete_run(self, run_id):
        self.calls.append(("delete_run", run_id))
        if self.delete_error:
            raise self.delete_error
        if run_id in self.results:
            raise AsyncTaskError("it has associated results", status_code=400)
        del self.runs[run_id]


@pytest.fixture
def fake():
    """The signed-in caller's AsyncTask."""
    client = _FakeAsyncTask()
    with patch.object(service, "client_for", return_value=client):
        yield client


@contextmanager
def _cursors():
    yield Mock()


def _open_cursor():
    return _cursors()


# --- which client -----------------------------------------------------------------------


def test_without_asynctask_there_are_no_runs_to_manage() -> None:
    """A 404 at the endpoint: this environment stores no runs."""
    with (
        patch.object(service, "asynctask_configured", return_value=False),
        pytest.raises(service.RunsNotStored),
    ):
        service.client_for(Mock())
    assert issubclass(service.RunsNotStored, service.RunNotFound)


def test_an_anonymous_caller_has_no_runs() -> None:
    """AsyncTask authenticates every call, so there is no one to list runs as."""
    with (
        patch.object(service, "asynctask_configured", return_value=True),
        patch.object(service, "asynctask_client_for", return_value=None),
        pytest.raises(SignInRequired),
    ):
        service.client_for(None)


# --- listing --------------------------------------------------------------------------------


def test_only_geneweaver_tool_runs_are_listed_newest_first(fake) -> None:
    """AsyncTask lists every plugin's runs; the workflow id tells ours apart."""
    fake.add(1, started=_at(hours=3), description=_record("upset", (1, 2)))
    fake.add(2, started=_at(hours=1), description=_record("mset", (3, 4)))
    fake.add(3, started=_at(hours=2), workflow="ats:StrainRecommendation:")

    listed = service.list_runs(Mock(), now=NOW)

    assert [run["run_id"] for run in listed["runs"]] == [2, 1]
    assert listed["total"] == 2
    assert listed["runs"][0] == {
        "run_id": 2,
        "tool": "mset",
        "name": "run 2",
        "geneset_ids": [3, 4],
        "status": "completed",
        "stalled": False,
        "problem": None,
        "created": _at(hours=1),
        "can_rerun": True,
    }


def test_the_list_is_paged(fake) -> None:
    """Total counts every run; the page is a slice of them, newest first."""
    for run_id in range(1, 6):
        fake.add(run_id, started=_at(hours=10 - run_id))

    listed = service.list_runs(Mock(), limit=2, offset=1, now=NOW)

    assert [run["run_id"] for run in listed["runs"]] == [4, 3]
    assert listed["total"] == 5


def test_a_run_without_a_record_is_listed_but_cannot_be_rerun(fake) -> None:
    """Runs from before G3-801, or free-text descriptions, still show."""
    fake.add(1, description="notes")

    run = service.list_runs(Mock(), now=NOW)["runs"][0]

    assert (run["tool"], run["geneset_ids"], run["can_rerun"]) == (None, None, False)


def test_runs_past_retention_are_deleted_as_the_caller_when_listing(fake) -> None:
    """AsyncTask keeps runs forever; their owner expires them (TOOL_RUN_RETENTION_DAYS)."""
    fake.add(1, started=_at(days=91))
    fake.add(2, started=_at(days=89))

    listed = service.list_runs(Mock(), now=NOW)

    assert [run["run_id"] for run in listed["runs"]] == [2]
    assert (listed["expired"], listed["retention_days"]) == (1, 90)
    assert 1 not in fake.runs
    assert ("delete_result", 901) in fake.calls


def test_a_run_that_cannot_be_expired_does_not_cost_the_list(fake) -> None:
    """Expiry is housekeeping: a failure is logged and the run stays listed."""
    fake.add(1, started=_at(days=200))
    fake.delete_error = AsyncTaskError("down", status_code=503)

    listed = service.list_runs(Mock(), now=NOW)

    assert [run["run_id"] for run in listed["runs"]] == [1]
    assert listed["expired"] == 0


# --- stalled and failed runs (G3-739) -----------------------------------------------------


def test_a_run_running_past_the_limit_is_stalled_with_an_explanation(fake) -> None:
    """AsyncTask sets no workflow timeout: a workflow that never starts runs forever."""
    fake.add(1, status="running", started=_at(minutes=46))
    fake.add(2, status="running", started=_at(minutes=10))

    runs = {run["run_id"]: run for run in service.list_runs(Mock(), now=NOW)["runs"]}

    assert runs[1]["stalled"] is True
    assert runs[1]["status"] == "running"
    assert "never started" in runs[1]["problem"]
    assert (runs[2]["stalled"], runs[2]["problem"]) == (False, None)


def test_a_failed_run_says_what_is_known_of_it(fake) -> None:
    """AsyncTask records no reason; the API says so rather than inventing one."""
    fake.add(1, status="failed")

    run = service.list_runs(Mock(), now=NOW)["runs"][0]

    assert run["status"] == "failed"
    assert "only that it failed" in run["problem"]


@pytest.mark.parametrize("init_time", [None, "yesterday", 5])
def test_a_run_with_no_usable_start_time_is_never_stalled_or_expired(init_time) -> None:
    """Without a start time there is nothing to measure."""
    assert service.run_problem("running", init_time, NOW) == (False, None)


# --- delete ------------------------------------------------------------------------------


def test_a_running_run_is_cancelled_then_its_result_and_it_deleted(fake) -> None:
    """AsyncTask refuses to delete a run with a result, and deleting does not stop it."""
    fake.add(1, status="running")
    fake.results[1] = {"id": 901, "values": {}}

    service.delete_run(Mock(), 1)

    mutations = [c for c in fake.calls if c[0] in ("cancel", "delete_result", "delete_run")]
    assert mutations == [("cancel", 1), ("delete_result", 901), ("delete_run", 1)]
    assert 1 not in fake.runs


def test_a_run_that_stopped_before_the_cancel_is_still_deleted(fake) -> None:
    """AsyncTask answers 400 to cancelling a run that is no longer running."""
    fake.add(1, status="running")
    fake.cancel_error = AsyncTaskError("not running", status_code=400)

    service.delete_run(Mock(), 1)

    assert 1 not in fake.runs


def test_another_plugins_run_is_not_ours_to_delete(fake) -> None:
    """Only GeneWeaver tool runs are managed here."""
    fake.add(1, workflow="ats:StrainRecommendation:")

    with pytest.raises(service.RunNotFound):
        service.delete_run(Mock(), 1)
    assert 1 in fake.runs


def test_runs_older_than_n_days_are_deleted_and_counted(fake) -> None:
    """The caller's own bulk delete; a failure is the caller's to see."""
    fake.add(1, started=_at(days=10))
    fake.add(2, started=_at(days=10), status="running")
    fake.add(3, started=_at(days=2))

    assert service.delete_runs_older_than(Mock(), 7, now=NOW) == 2
    assert list(fake.runs) == [3]

    fake.add(4, started=_at(days=10))
    fake.delete_error = AsyncTaskError("down", status_code=503)
    with pytest.raises(AsyncTaskError):
        service.delete_runs_older_than(Mock(), 7, now=NOW)


# --- read, with access checked again (G3-736) ------------------------------------------------


def test_a_completed_run_is_read_after_its_gene_sets_are_checked(fake) -> None:
    """The caller must still be able to read the run's gene sets."""
    fake.add(1, description=_record("upset", (5, 6)), result={"intersections": []})
    with patch.object(service, "_gate_geneset_access") as gate:
        run = service.read_run(_open_cursor, Mock(), 1, now=NOW)

    assert gate.call_args.args[2] == [5, 6]
    assert run["result"] == {"intersections": []}
    assert (run["tool"], run["geneset_ids"], run["can_rerun"]) == ("upset", [5, 6], True)
    assert run["withheld_genesets"] == 0


def test_a_result_whose_gene_sets_are_no_longer_readable_is_refused(fake) -> None:
    """Access lost since the run means no result (403), whoever owns the run."""
    fake.add(1, description=_record("upset", (5,)))
    with (
        patch.object(
            service, "_gate_geneset_access", side_effect=UnauthorizedException(detail="5")
        ),
        pytest.raises(UnauthorizedException),
    ):
        service.read_run(_open_cursor, Mock(), 1, now=NOW)


def test_gene_sets_a_result_names_are_withheld_once_unreadable(fake) -> None:
    """ABBA and Similar gene sets list gene sets beyond the input."""
    result = {"genesets": [{"gs_id": 10}, {"gs_id": 11}, {"gs_id": 12}], "genes": []}
    fake.add(1, description=_record("abba", (), genes=["Drd2"]), result=result)
    with (
        patch.object(service, "_gate_geneset_access"),
        patch.object(service.db_geneset, "readable_ids", return_value={10, 12}) as readable,
    ):
        run = service.read_run(_open_cursor, Mock(id=7), 1, now=NOW)

    assert readable.call_args.args[2] == [10, 11, 12]
    assert run["result"]["genesets"] == [{"gs_id": 10}, {"gs_id": 12}]
    assert run["withheld_genesets"] == 1


def test_a_run_without_a_record_is_checked_by_its_envelopes_gene_sets(fake) -> None:
    """Runs from before G3-801 carry their gene set ids, as strings, in the envelope."""
    fake.add(
        1, values={"values": {"tool": "jaccard_similarity", "input": {"geneset_ids": ["5", "6"]}}}
    )
    with patch.object(service, "_gate_geneset_access") as gate:
        run = service.read_run(_open_cursor, Mock(), 1, now=NOW)

    assert gate.call_args.args[2] == [5, 6]
    assert (run["tool"], run["can_rerun"]) == ("jaccard_similarity", False)


def test_a_completed_run_whose_gene_sets_cannot_be_found_is_not_returned(fake) -> None:
    """Fail closed: a result whose access cannot be checked is not handed out."""
    fake.add(1, values={"tool": "mset", "input": {}})

    with pytest.raises(service.RunNotReadable):
        service.read_run(_open_cursor, Mock(), 1, now=NOW)
    assert ("get_result", 1) not in fake.calls


def test_a_running_run_is_read_without_a_connection_or_its_result(fake) -> None:
    """Polling touches no database until there is a result to check."""
    fake.add(1, status="running", description=_record())
    opened = Mock(side_effect=AssertionError("no cursor while running"))

    run = service.read_run(opened, Mock(), 1, now=NOW)

    assert (run["status"], run["result"]) == ("running", None)
    assert ("get_result", 1) not in fake.calls


def test_another_plugins_run_is_not_read(fake) -> None:
    """A strain recommender run of the same user is not a GeneWeaver run."""
    fake.add(1, workflow="ats:StrainRecommendation:")

    with pytest.raises(service.RunNotFound):
        service.read_run(_open_cursor, Mock(), 1, now=NOW)


# --- rerun --------------------------------------------------------------------------------


def test_a_tool_run_is_rerun_through_the_gate_with_its_recorded_request(fake) -> None:
    """Resolved and gated again, as a new run."""
    description = RunRecord(
        tool="jaccard_similarity",
        geneset_ids=[5, 6],
        request={"geneset_ids": [5, 6], "parameters": {"p_value_threshold": 0.05}},
    ).to_description()
    fake.add(1, description=description)
    with (
        patch.object(service, "precheck_run"),
        patch.object(service, "prepare_tool_run") as prepare,
        patch.object(service, "execute_tool_run", return_value={"run_id": 2, "result": {}}),
    ):
        output = service.rerun(_open_cursor, Mock(), 1)

    assert prepare.call_args.kwargs["tool_name"] == "jaccard_similarity"
    assert prepare.call_args.kwargs["geneset_ids"] == [5, 6]
    assert prepare.call_args.kwargs["parameters"] == {"p_value_threshold": 0.05}
    assert (output["run_id"], output["rerun_of"]) == (2, 1)


def test_abba_is_rerun_through_its_own_service_and_signed_again(fake) -> None:
    """ABBA's signed identity expires, so it is never resubmitted as it was."""
    request = {"genes": ["Drd2"], "geneset_ids": [5]}
    fake.add(1, description=RunRecord("abba", [5], request).to_description())
    from geneweaver.api.services import abba as abba_service

    with patch.object(abba_service, "run_abba", return_value={"run_id": 2}) as run_abba:
        output = service.rerun(_open_cursor, Mock(), 1)

    request = run_abba.call_args.args[1]
    assert (request.genes, request.geneset_ids) == (["Drd2"], [5])
    assert output["rerun_of"] == 1


def test_a_rerun_still_running_says_what_it_reruns(fake) -> None:
    """The 202 body names the original too."""
    fake.add(1, description=_record())
    pending = ToolRunPending({"tool": "upset", "geneset_ids": [1, 2]}, 2, "running")
    with (
        patch.object(service, "precheck_run"),
        patch.object(service, "prepare_tool_run"),
        patch.object(service, "execute_tool_run", side_effect=pending),
        pytest.raises(ToolRunPending) as raised,
    ):
        service.rerun(_open_cursor, Mock(), 1)

    assert raised.value.body["rerun_of"] == 1
    assert raised.value.body["run_id"] == 2


def test_a_run_without_a_record_cannot_be_rerun(fake) -> None:
    """Its envelope is resolved data and, for ABBA, an expired identity: not a request."""
    fake.add(1)

    with pytest.raises(service.RunNotRerunnable):
        service.rerun(_open_cursor, Mock(), 1)


def test_a_recorded_request_that_no_longer_validates_is_a_request_error(fake) -> None:
    """E.g. a schema that tightened since the run: a 422, not a crash."""
    fake.add(1, description=_record("similar_genesets", (5,), geneset_id=0))

    with pytest.raises(ToolRequestError):
        service.rerun(_open_cursor, Mock(), 1)
