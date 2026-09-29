"""Tests for the tool worker's configuration."""

import pytest
from geneweaver.tools.temporal import worker
from geneweaver.tools.temporal.routing import (
    NATIVE_PROFILE,
    NATIVE_TASK_QUEUE,
    PYTHON_PROFILE,
    PYTHON_TASK_QUEUE,
)
from geneweaver.tools.temporal.worker import (
    DEFAULT_MAX_CONCURRENT_ACTIVITIES,
    max_concurrent_activities,
    task_queue,
)


def test_each_profile_consumes_its_own_queue() -> None:
    """Two deployments, two queues -- the reason the workers are separate at all."""
    assert task_queue(PYTHON_PROFILE) == PYTHON_TASK_QUEUE
    assert task_queue(NATIVE_PROFILE) == NATIVE_TASK_QUEUE
    assert PYTHON_TASK_QUEUE != NATIVE_TASK_QUEUE


def test_concurrency_defaults_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unconfigured worker still gets a sane cap."""
    monkeypatch.delenv(worker.MAX_CONCURRENT_ENV_VAR, raising=False)
    assert max_concurrent_activities() == DEFAULT_MAX_CONCURRENT_ACTIVITIES


def test_concurrency_is_environment_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operational limits come from the environment."""
    monkeypatch.setenv(worker.MAX_CONCURRENT_ENV_VAR, "12")
    assert max_concurrent_activities() == 12


@pytest.mark.parametrize("value", ["nonsense", "0", "-3", "2.5"])
def test_an_unusable_concurrency_falls_back(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bad value must not stop the worker starting.

    Unlike the profile, there is a safe default here, and refusing to start would take tool
    runs down for a typo.
    """
    monkeypatch.setenv(worker.MAX_CONCURRENT_ENV_VAR, value)
    assert max_concurrent_activities() == DEFAULT_MAX_CONCURRENT_ACTIVITIES


def test_the_default_concurrency_is_conservative() -> None:
    """A tool run can saturate a core for minutes; throughput comes from replicas.

    asynctask-mpd-plugin settled on 5 per pod for the same reason.
    """
    assert 1 <= DEFAULT_MAX_CONCURRENT_ACTIVITIES <= 10


def test_the_worker_registers_the_workflow_and_activity() -> None:
    """What the worker passes to Temporal must be what the plugin declares."""
    from geneweaver.tools.temporal import ACTIVITIES, WORKFLOWS
    from geneweaver.tools.temporal.activities import ACTIVITY_NAME

    assert [w.__name__ for w in WORKFLOWS] == ["GeneWeaverToolWorkflow"]
    assert [a.__temporal_activity_definition.name for a in ACTIVITIES] == [ACTIVITY_NAME]


def test_the_activity_worker_constructs_with_a_real_executor() -> None:
    """`run_tool` is synchronous, so Temporal demands an `activity_executor`.

    Without one the `Worker` constructor raises and the pod crash-loops. Asserting which
    callables appear in `ACTIVITIES` could not catch that, so this exercises the SDK's own
    validation -- the same check that rejected the first version of this worker.
    """
    from concurrent.futures import ThreadPoolExecutor

    from geneweaver.tools.temporal import ACTIVITIES
    from temporalio.converter import DataConverter
    from temporalio.worker._activity import _ActivityWorker

    with ThreadPoolExecutor(max_workers=2) as executor:
        _ActivityWorker(
            bridge_worker=lambda: None,
            task_queue="test",
            activities=ACTIVITIES,
            activity_executor=executor,
            shared_state_manager=None,
            data_converter=DataConverter.default,
            interceptors=[],
            metric_meter=None,
            client=None,
            encode_headers=False,
        )


def test_omitting_the_executor_is_what_the_sdk_rejects() -> None:
    """Pins the reason the executor is required, so it is not dropped as boilerplate."""
    from geneweaver.tools.temporal import ACTIVITIES
    from temporalio.converter import DataConverter
    from temporalio.worker._activity import _ActivityWorker

    with pytest.raises(ValueError, match="not async so an activity_executor must be present"):
        _ActivityWorker(
            bridge_worker=lambda: None,
            task_queue="test",
            activities=ACTIVITIES,
            activity_executor=None,
            shared_state_manager=None,
            data_converter=DataConverter.default,
            interceptors=[],
            metric_meter=None,
            client=None,
            encode_headers=False,
        )


def test_the_activity_opts_out_of_thread_cancel_injection() -> None:
    """Injected `CancelledError` can unwind `run_binary` at an arbitrary point.

    `Popen.__exit__` waits for the child rather than killing it, so the binary would outlive
    the activity. Cancellation is observed cooperatively through the progress hook instead.
    """
    from geneweaver.tools.temporal.activities import run_tool

    assert run_tool.__temporal_activity_definition.no_thread_cancel_exception is True
