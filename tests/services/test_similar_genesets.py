"""Tests for the Similar gene sets service: AsyncTask where configured, in-process otherwise."""

from contextlib import contextmanager
from unittest.mock import MagicMock, Mock, patch

import pytest
from geneweaver.tools.abba.identity import verified_user_id

from geneweaver.api.schemas.tools import SimilarGenesetsRequest
from geneweaver.api.services import similar_genesets as service
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
    """An `open_cursor` that records whether a cursor is open."""

    def __init__(self) -> None:
        self.open = False
        self.cursor = MagicMock()

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


def test_a_search_is_submitted_to_asynctask_with_the_caller_signed() -> None:
    """Visible in Temporal like every tool; the user travels signed, beside the input."""
    fake = _FakeAsyncTask(result={"genesets": []})
    with _on_asynctask(fake):
        result = service.run_similar_genesets(
            _Cursors(), SimilarGenesetsRequest(geneset_id=5, threshold="uploader"), Mock(id=7)
        )
    assert fake.envelope["tool"] == "similar_genesets"
    assert fake.envelope["input"]["geneset_id"] == 5
    assert fake.envelope["input"]["threshold"] == "uploader"
    assert "user_id" not in fake.envelope["input"]
    assert verified_user_id(fake.envelope["identity"], SECRET) == 7
    assert fake.name == "similar_genesets: GS5"
    assert result["executed_by"] == "asynctask"
    assert result["thresholds"] == {"threshold": "uploader"}
    assert result["result"] == {"genesets": []}


def test_an_unreadable_gene_set_is_refused_before_submission() -> None:
    """No one learns what a gene set they cannot read is like."""
    fake = _FakeAsyncTask()
    with (
        _on_asynctask(fake),
        patch.object(tool_service.db_geneset, "is_readable", return_value=False),
        pytest.raises(tool_service.UnauthorizedException),
    ):
        service.run_similar_genesets(_Cursors(), SimilarGenesetsRequest(geneset_id=5), Mock(id=7))
    assert fake.envelope is None


def test_the_connection_is_returned_before_waiting_on_asynctask() -> None:
    """A search takes minutes; the pooled connection must not wait with it."""
    cursors = _Cursors()
    seen = []

    class Recording(_FakeAsyncTask):
        def submit(self, envelope, name):
            seen.append(cursors.open)
            return super().submit(envelope, name)

    with _on_asynctask(Recording(result={})):
        service.run_similar_genesets(cursors, SimilarGenesetsRequest(geneset_id=5), Mock(id=7))
    assert seen == [False]


def test_a_long_search_is_handed_back_by_run_id() -> None:
    """Searches take about two minutes, past the API's wait, so the page polls."""
    with (
        _on_asynctask(_FakeAsyncTask(final_status="running")),
        pytest.raises(tool_service.ToolRunPending) as pending,
    ):
        service.run_similar_genesets(_Cursors(), SimilarGenesetsRequest(geneset_id=5), Mock(id=7))
    assert pending.value.body["tool"] == "similar_genesets"
    assert pending.value.body["run_id"] == 11


def test_anonymous_is_refused_before_a_connection_is_leased() -> None:
    """Running a search requires signing in, checked before the pool is touched."""
    open_cursor = Mock()
    with pytest.raises(tool_service.SignInRequired):
        service.run_similar_genesets(open_cursor, SimilarGenesetsRequest(geneset_id=5), None)
    open_cursor.assert_not_called()


def test_without_asynctask_the_search_runs_here_one_at_a_time() -> None:
    """Same search function as the worker's; a second concurrent one is refused, not queued."""
    cursors = _Cursors()
    output = Mock(model_dump=Mock(return_value={"genesets": []}))
    with (
        patch.object(service, "asynctask_client_for", return_value=None),
        patch.object(service, "search", return_value=output) as search,
    ):
        result = service.run_similar_genesets(
            cursors, SimilarGenesetsRequest(geneset_id=5), Mock(id=7)
        )
        connection, tool_input, user_id = search.call_args.args
        assert connection is cursors.cursor.connection
        assert (tool_input.geneset_id, user_id) == (5, 7)
        assert result["executed_by"] == "in_process"

        assert service._running.acquire(blocking=False)
        try:
            with pytest.raises(service.SimilarGenesetsBusy):
                service.run_similar_genesets(
                    cursors, SimilarGenesetsRequest(geneset_id=5), Mock(id=7)
                )
        finally:
            service._running.release()
