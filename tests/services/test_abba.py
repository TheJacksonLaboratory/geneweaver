"""Tests for the ABBA search service: AsyncTask where configured, in-process otherwise."""

import threading
from contextlib import contextmanager
from unittest.mock import MagicMock, Mock, patch

import pytest
from geneweaver.tools.abba.identity import verified_user_id
from psycopg.rows import tuple_row
from pydantic import ValidationError

from geneweaver.api.schemas.tools import ABBARequest
from geneweaver.api.services import abba as service
from geneweaver.api.services import tools as tool_service
from geneweaver.api.services.asynctask import RunState

SECRET = "db-password"


class _FakeAsyncTask:
    """Records the submission and replays a scripted outcome."""

    def __init__(self, final_status: str = "completed", result: dict | None = None) -> None:
        self.final = RunState(run_id=11, workflow_id="ats:GeneWeaverTools:x", status=final_status)
        self.final.result = result
        self.envelope = None
        self.name = None

    def submit(self, envelope, name):
        self.envelope, self.name = envelope, name
        return RunState(run_id=11, workflow_id="ats:GeneWeaverTools:x", status="running")

    def wait(self, state, timeout, poll_interval):
        return self.final


class _Cursors:
    """An `open_cursor` that records whether a cursor is open, and the seed-gene query."""

    def __init__(self, seed_rows: list | None = None) -> None:
        self.open = False
        self.cursor = MagicMock()
        rows = self.cursor.connection.cursor.return_value.__enter__.return_value
        rows.fetchall.return_value = seed_rows or []
        self.rows = rows

    @contextmanager
    def __call__(self):
        self.open = True
        try:
            yield self.cursor
        finally:
            self.open = False


@pytest.fixture(autouse=True)
def _readable_and_keyed(monkeypatch):
    """Every gene set readable; the API's database password is the signing secret."""
    monkeypatch.setattr(service.settings, "DB_PASSWORD", SECRET)
    with patch.object(tool_service.db_geneset, "is_readable", return_value=True):
        yield


def _on_asynctask(fake):
    return patch.object(service, "asynctask_client_for", return_value=fake)


def test_a_search_is_submitted_to_asynctask_as_the_tool_workflow() -> None:
    """ABBA goes through AsyncTask like every tool, so the run is visible in Temporal."""
    fake = _FakeAsyncTask(result={"tool": "abba", "genes": []})
    with _on_asynctask(fake):
        result = service.run_abba(_Cursors(), ABBARequest(genes=["Drd2", "Drd1"]), Mock(id=7))

    assert fake.envelope["tool"] == "abba"
    assert fake.envelope["input"]["genes"] == ["Drd2", "Drd1"]
    assert fake.name == "abba: Drd2, Drd1"
    assert result["executed_by"] == "asynctask"
    assert result["run_id"] == 11
    assert result["result"] == {"tool": "abba", "genes": []}


def test_the_caller_is_sent_signed_not_in_the_input() -> None:
    """The worker trusts only a signed identity, so a forged user id cannot be submitted."""
    fake = _FakeAsyncTask(result={})
    with _on_asynctask(fake):
        service.run_abba(_Cursors(), ABBARequest(genes=["Drd2"]), Mock(id=7))

    assert "user_id" not in fake.envelope["input"]
    assert verified_user_id(fake.envelope["identity"], SECRET) == 7
    forged = {**fake.envelope["identity"], "user_id": 8}
    with pytest.raises(ValueError, match="does not verify"):
        verified_user_id(forged, SECRET)


def test_seed_gene_sets_are_gated_then_expanded_to_genes() -> None:
    """The worker gets genes, never a gene set id to read on the caller's behalf."""
    cursors = _Cursors(seed_rows=[("Th",), ("Drd2",)])
    fake = _FakeAsyncTask(result={})
    with (
        _on_asynctask(fake),
        patch.object(service, "_gate_geneset_access") as gate,
    ):
        service.run_abba(cursors, ABBARequest(genes=["drd2"], geneset_ids=[5]), Mock(id=7))

    assert gate.call_args.args[2] == [5]
    cursors.cursor.connection.cursor.assert_called_with(row_factory=tuple_row)
    assert cursors.rows.execute.call_args.args[1] == {"gs_ids": [5]}
    # Repeats are dropped case-insensitively, the typed gene first.
    assert fake.envelope["input"]["genes"] == ["drd2", "Th"]
    assert "geneset_ids" not in fake.envelope["input"]


def test_an_unreadable_seed_gene_set_is_refused_before_submission() -> None:
    """The gate runs before anything reaches AsyncTask."""
    fake = _FakeAsyncTask()
    with (
        _on_asynctask(fake),
        patch.object(tool_service.db_geneset, "is_readable", return_value=False),
        pytest.raises(tool_service.UnauthorizedException),
    ):
        service.run_abba(_Cursors(), ABBARequest(geneset_ids=[5]), Mock(id=7))
    assert fake.envelope is None


def test_the_connection_is_returned_before_waiting_on_asynctask() -> None:
    """A search waits up to 30 s; holding a pooled connection through that starves the pool."""
    cursors = _Cursors()
    seen = []

    class Recording(_FakeAsyncTask):
        def submit(self, envelope, name):
            seen.append(cursors.open)
            return super().submit(envelope, name)

    with _on_asynctask(Recording(result={})):
        service.run_abba(cursors, ABBARequest(genes=["Drd2"]), Mock(id=7))
    assert seen == [False]


def test_a_long_search_is_handed_back_by_run_id() -> None:
    """Searches take 20-60 s, past the API's wait, so the client polls like any tool."""
    with (
        _on_asynctask(_FakeAsyncTask(final_status="running")),
        pytest.raises(tool_service.ToolRunPending) as pending,
    ):
        service.run_abba(_Cursors(), ABBARequest(genes=["Drd2"]), Mock(id=7))
    assert pending.value.body["tool"] == "abba"
    assert pending.value.body["run_id"] == 11


def test_a_failed_search_names_its_workflow() -> None:
    """AsyncTask records no cause, so the workflow id is how to find one."""
    with (
        _on_asynctask(_FakeAsyncTask(final_status="failed")),
        pytest.raises(tool_service.ToolRunFailed, match="ats:GeneWeaverTools:x"),
    ):
        service.run_abba(_Cursors(), ABBARequest(genes=["Drd2"]), Mock(id=7))


def test_anonymous_is_refused_before_a_connection_is_leased() -> None:
    """Running a search requires signing in, checked before the pool is touched."""
    open_cursor = Mock()
    with pytest.raises(tool_service.SignInRequired):
        service.run_abba(open_cursor, ABBARequest(genes=["Drd2"]), user=None)
    open_cursor.assert_not_called()


# --- In-process, where AsyncTask is not configured -------------------------------------


def _in_process():
    return patch.object(service, "asynctask_client_for", return_value=None)


def test_without_asynctask_the_search_runs_here_on_the_pooled_connection() -> None:
    """Same search function as the worker's, on the request's connection."""
    cursors = _Cursors()
    output = Mock(model_dump=Mock(return_value={"tool": "abba"}))
    with _in_process(), patch.object(service, "search", return_value=output) as search:
        result = service.run_abba(cursors, ABBARequest(genes=["Drd2"]), Mock(id=7))

    connection, tool_input, user_id = search.call_args.args
    assert connection is cursors.cursor.connection
    assert tool_input.genes == ["Drd2"]
    assert user_id == 7
    assert search.call_args.kwargs["statement_timeout_seconds"] == 240
    assert result == {
        "tool": "abba",
        "geneset_ids": [],
        "gene_counts": {},
        "caveat": None,
        "executed_by": "in_process",
        "run_id": None,
        "result": {"tool": "abba"},
    }


def test_a_search_over_the_limit_is_refused_not_queued() -> None:
    """A search past the limit must not wait on the pool."""
    open_cursor = Mock()
    full = threading.BoundedSemaphore(1)
    full.acquire()
    with (
        _in_process(),
        patch.object(service, "_running", full),
        pytest.raises(service.ABBABusy),
    ):
        service.run_abba(open_cursor, ABBARequest(genes=["Drd2"]), user=Mock(id=7))
    open_cursor.assert_not_called()


def test_the_slot_is_released_when_a_search_fails() -> None:
    """A failed search must not leak its slot."""
    slot = threading.BoundedSemaphore(1)
    with (
        _in_process(),
        patch.object(service, "_running", slot),
        patch.object(service, "search", side_effect=RuntimeError("query failed")),
        pytest.raises(RuntimeError),
    ):
        service.run_abba(_Cursors(), ABBARequest(genes=["Drd2"]), Mock(id=7))
    assert slot.acquire(blocking=False)


# --- The request ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {},  # no seed at all
        {"genes": ["  ", ""]},  # blanks are not a seed
        {"genes": ["Drd2"], "tiers": []},
        {"genes": ["Drd2"], "tiers": [6]},
        {"genes": ["Drd2"], "min_genes": 0},
        {"genes": ["Drd2"], "min_genesets": 0},
        {"genes": ["Drd2"], "species_ids": []},
        {"genes": ["x"] * 1001},
    ],
)
def test_request_rejects(body) -> None:
    """Requests the search cannot run are refused."""
    with pytest.raises(ValidationError):
        ABBARequest(**body)


def test_request_cleans_genes_case_insensitively() -> None:
    """Repeats and blanks are dropped; tiers are normalised."""
    request = ABBARequest(genes=[" Drd2", "drd2", "Drd1", ""], tiers=[3, 1, 1])
    assert request.genes == ["Drd2", "Drd1"]
    assert request.tiers == [1, 3]


def test_request_accepts_gene_sets_alone() -> None:
    """A gene set alone is a valid seed."""
    assert ABBARequest(geneset_ids=[167180]).genes == []
