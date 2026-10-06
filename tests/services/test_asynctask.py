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
