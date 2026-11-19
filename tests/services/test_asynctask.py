"""Tests for the AsyncTask run client.

The shapes here are AsyncTask's, read from its code: a `jax.apiutils` envelope with the
payload under ``object``, and the run status as Temporal's `WorkflowExecutionStatus`
integer.
"""

from unittest.mock import Mock

import pytest
import requests

from geneweaver.api.services.asynctask import (
    TASK_TYPE,
    AsyncTaskClient,
    AsyncTaskError,
    RunState,
    status_name,
)


def _response(status_code: int, obj: dict | None = None, text: str = "") -> Mock:
    response = Mock(status_code=status_code, text=text)
    response.json.return_value = {"object": obj, "info": None, "errors": None}
    return response


def _client(*responses) -> tuple[AsyncTaskClient, Mock]:
    session = Mock()
    session.request.side_effect = list(responses)
    return AsyncTaskClient("http://ats/asynctask/api/", "tok", session=session), session


def test_submit_posts_the_envelope_as_the_user() -> None:
    """The envelope goes through verbatim as `values`, under our plugin's task type."""
    client, session = _client(_response(200, {"id": 7, "workflow_id": "ats:x", "status": 1}))
    envelope = {"tool": "upset", "input": {"geneset_ids": ["1", "2"]}}

    state = client.submit(envelope, name="upset: 1, 2")

    assert state == RunState(run_id=7, workflow_id="ats:x", status="running")
    method, url = session.request.call_args.args
    kwargs = session.request.call_args.kwargs
    assert (method, url) == ("POST", "http://ats/asynctask/api/runs")
    assert kwargs["json"] == {"task_type": TASK_TYPE, "name": "upset: 1, 2", "values": envelope}
    assert kwargs["headers"] == {"Authorization": "Bearer tok"}


def test_get_reads_the_result_only_once_completed() -> None:
    """A completed run's output is the stored result's `values`."""
    client, session = _client(
        _response(200, {"id": 7, "workflow_id": "w", "status": 2}),
        _response(200, {"run_id": 7, "values": {"intersections": []}}),
    )

    state = client.get(7)

    assert state.status == "completed"
    assert state.result == {"intersections": []}
    assert [call.args[1] for call in session.request.call_args_list] == [
        "http://ats/asynctask/api/runs/7",
        "http://ats/asynctask/api/runs/7/results",
    ]


def test_get_does_not_fetch_a_result_for_a_failed_run() -> None:
    """Get does not fetch a result for a failed run."""
    client, session = _client(_response(200, {"id": 7, "workflow_id": "w", "status": 3}))

    state = client.get(7)

    assert state.status == "failed"
    assert state.finished
    assert state.result is None
    assert session.request.call_count == 1


def test_refusals_keep_asynctasks_status_code() -> None:
    """An ownership refusal must stay distinguishable from an outage."""
    client, _ = _client(_response(403, text='{"detail":"Unauthorized."}'))

    with pytest.raises(AsyncTaskError) as raised:
        client.get(7)

    assert raised.value.status_code == 403


def test_an_unreachable_asynctask_is_an_asynctask_error() -> None:
    """An unreachable asynctask is an asynctask error."""
    client, _ = _client(requests.ConnectionError("refused"))

    with pytest.raises(AsyncTaskError, match="unreachable") as raised:
        client.get(7)

    assert raised.value.status_code is None


def test_wait_polls_until_finished() -> None:
    """Wait polls until finished."""
    client, session = _client(
        _response(200, {"id": 7, "workflow_id": "w", "status": 1}),
        _response(200, {"id": 7, "workflow_id": "w", "status": 2}),
        _response(200, {"values": {"ok": True}}),
    )

    state = client.wait(RunState(7, "w", "running"), timeout=5, poll_interval=0)

    assert state.status == "completed"
    assert state.result == {"ok": True}
    assert session.request.call_count == 3


def test_wait_returns_a_still_running_run_at_the_deadline() -> None:
    """Running past the wait is not an error; the caller hands back the run id."""
    client, session = _client()

    state = client.wait(RunState(7, "w", "running"), timeout=0, poll_interval=0)

    assert state.status == "running"
    assert session.request.call_count == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, "running"),
        (2, "completed"),
        (7, "timed_out"),
        ("COMPLETED", "completed"),
        (99, "unknown(99)"),
    ],
)
def test_status_name(value, expected) -> None:
    """Status name."""
    assert status_name(value) == expected


# --- responses outside the contract become AsyncTaskError (502), not a crash (500) ---


def _raw(status_code: int, body=None, text: str = "") -> Mock:
    response = Mock(status_code=status_code, text=text)
    if isinstance(body, Exception):
        response.json.side_effect = body
    else:
        response.json.return_value = body
    return response


@pytest.mark.parametrize(
    ("response", "match"),
    [
        (_raw(200, ValueError("Expecting value"), text="<html>gateway</html>"), "not JSON"),
        (_raw(200, {"info": None}), "without an object"),
        (_raw(200, ["not", "an", "envelope"]), "without an object"),
        (_raw(200, {"object": {"workflow_id": "w", "status": 1}}), "missing its id"),
        (_raw(200, {"object": {"id": 7, "workflow_id": "w"}}), "missing its id or status"),
    ],
)
def test_a_malformed_success_is_an_asynctask_error(response, match) -> None:
    """An ingress error page served as 200, or a changed shape, is an upstream fault."""
    client, _ = _client(response)

    with pytest.raises(AsyncTaskError, match=match) as raised:
        client.submit({"tool": "upset", "input": {}}, name="x")

    assert raised.value.status_code is None


def test_a_completed_run_without_a_result_object_is_an_asynctask_error() -> None:
    """A completed run must come with its output, or there is nothing to return."""
    client, _ = _client(
        _response(200, {"id": 7, "workflow_id": "w", "status": 2}),
        _response(200, {"run_id": 7, "values": None}),
    )

    with pytest.raises(AsyncTaskError, match="without a result object"):
        client.get(7)


# --- the wait is a ceiling ----------------------------------------------------------


class _Clock:
    """A fake monotonic clock that advances only when slept on."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_wait_never_sleeps_past_its_budget(monkeypatch) -> None:
    """With 0.5s left and a 1s poll interval, it sleeps 0.5s and does not poll after."""
    clock = _Clock()
    monkeypatch.setattr("geneweaver.api.services.asynctask.time", clock)
    client, session = _client()

    state = client.wait(RunState(7, "w", "running"), timeout=0.5, poll_interval=1.0)

    assert state.status == "running"
    assert clock.sleeps == [0.5]
    assert session.request.call_count == 0


def test_wait_bounds_each_poll_by_what_remains(monkeypatch) -> None:
    """A poll gets the remainder of the budget, not the client's full per-call timeout."""
    clock = _Clock()
    monkeypatch.setattr("geneweaver.api.services.asynctask.time", clock)
    client, session = _client(_response(200, {"id": 7, "workflow_id": "w", "status": 1}))
    client.request_timeout = 10.0

    client.wait(RunState(7, "w", "running"), timeout=1.5, poll_interval=1.0)

    assert session.request.call_args_list[0].kwargs["timeout"] == pytest.approx(0.5)


def test_a_poll_that_times_out_is_still_running_not_an_outage() -> None:
    """The run is unaffected by a slow poll, so the caller hands back its id."""
    client, _ = _client(requests.Timeout("read timed out"))

    state = client.wait(RunState(7, "w", "running"), timeout=5, poll_interval=0)

    assert state.status == "running"
    assert state.run_id == 7


def test_a_submission_that_times_out_is_still_an_error() -> None:
    """Unlike a poll, a timed-out submission may or may not have created a run."""
    client, _ = _client(requests.Timeout("read timed out"))

    with pytest.raises(AsyncTaskError, match="timed out"):
        client.submit({"tool": "upset", "input": {}}, name="x")


# --- run management calls (G3-801) ---------------------------------------------------------


def _collection(status_code: int, data) -> Mock:
    response = Mock(status_code=status_code, text="")
    response.json.return_value = {"data": data, "paging": None, "info": None, "errors": None}
    return response


def _confirmed(status_code: int = 200, value=True) -> Mock:
    response = Mock(status_code=status_code, text="")
    response.json.return_value = {"object": value, "info": None, "errors": None}
    return response


def test_submit_keeps_the_request_as_the_inputs_description() -> None:
    """AsyncTask stores `description` with the input and returns it from GET /inputs."""
    client, session = _client(_response(200, {"id": 7, "workflow_id": "w", "status": 1}))

    client.submit({"tool": "upset", "input": {}}, name="upset: 1, 2", description="{...}")

    assert session.request.call_args.kwargs["json"]["description"] == "{...}"


def test_runs_and_inputs_are_read_from_collection_envelopes() -> None:
    """The list endpoints answer `{data: [...]}`, not `{object: ...}`."""
    client, session = _client(
        _collection(200, [{"id": 1, "workflow_id": "ats:GeneWeaverTools:x", "status": 2}]),
        _collection(200, [{"id": 4, "name": "n", "description": None}]),
    )

    assert client.list_runs()[0]["id"] == 1
    assert client.list_inputs()[0]["id"] == 4
    assert [call.args[1] for call in session.request.call_args_list] == [
        "http://ats/asynctask/api/runs",
        "http://ats/asynctask/api/inputs",
    ]


@pytest.mark.parametrize("body", [{"data": None}, {"data": [1]}, ["x"], {"object": {}}])
def test_a_malformed_collection_is_an_asynctask_error(body) -> None:
    """Anything but a list of objects under `data` is outside the contract."""
    response = Mock(status_code=200, text="")
    response.json.return_value = body
    client, _ = _client(response)

    with pytest.raises(AsyncTaskError, match="collection"):
        client.list_runs()


def test_the_owner_unchecked_workflow_id_filter_is_never_used() -> None:
    """At 5f2acea, GET /runs?workflow_id= returns a run without checking its owner."""
    client, session = _client(_collection(200, []))

    client.list_runs()

    assert "workflow_id" not in session.request.call_args.args[1]
    assert "params" not in session.request.call_args.kwargs


def test_a_runs_result_id_is_none_when_it_has_no_result() -> None:
    """AsyncTask answers 404 for a run with no stored result."""
    client, _ = _client(
        _response(200, {"id": 31, "run_id": 7, "values": {}}),
        _response(404, text='{"detail":"Result not found."}'),
    )

    assert client.result_id(7) == 31
    assert client.result_id(8) is None


def test_deletes_and_cancel_use_asynctasks_routes() -> None:
    """Cancel answers the run; deletes answer `object: true`."""
    client, session = _client(
        _response(200, {"id": 7, "workflow_id": "w", "status": 4}),
        _confirmed(),
        _confirmed(),
    )

    assert client.cancel(7).status == "cancelled"
    client.delete_result(31)
    client.delete_run(7)

    assert [call.args for call in session.request.call_args_list] == [
        ("POST", "http://ats/asynctask/api/runs/7/cancel"),
        ("DELETE", "http://ats/asynctask/api/results/31"),
        ("DELETE", "http://ats/asynctask/api/runs/7"),
    ]


@pytest.mark.parametrize("value", [False, None, {"ok": True}])
def test_a_delete_not_confirmed_is_an_asynctask_error(value) -> None:
    """Only `object: true` is a delete done."""
    client, _ = _client(_confirmed(value=value))

    with pytest.raises(AsyncTaskError, match="did not confirm"):
        client.delete_run(7)


def test_a_refused_delete_keeps_asynctasks_status() -> None:
    """E.g. 400 for a run that still has its result, so the caller can tell."""
    client, _ = _client(_response(400, text='{"detail":"it has associated results"}'))

    with pytest.raises(AsyncTaskError) as raised:
        client.delete_run(7)
    assert raised.value.status_code == 400


def test_a_runs_start_time_is_kept() -> None:
    """`init_time` dates a run for stall detection and retention."""
    client, _ = _client(
        _response(
            200, {"id": 7, "workflow_id": "w", "status": 1, "init_time": "2026-11-19T10:00:00"}
        )
    )

    assert client.get_status(7).init_time == "2026-11-19T10:00:00"
