"""Tests for the tool worker's configuration."""

import contextlib

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


def test_the_plugin_declares_the_workflow_and_activity() -> None:
    """What the plugin exports must be what AsyncTask and our worker expect."""
    from geneweaver.tools.temporal import ACTIVITIES, WORKFLOWS
    from geneweaver.tools.temporal.activities import ACTIVITY_NAME

    assert [w.__name__ for w in WORKFLOWS] == ["GeneWeaverToolWorkflow"]
    assert [a.__temporal_activity_definition.name for a in ACTIVITIES] == [ACTIVITY_NAME]


def test_the_worker_serves_activities_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Orchestration belongs to AsyncTask; this process only computes.

    `asynctask-mpd-plugin`'s workers register activities alone for the same reason -- the
    workflow runs where the plugin is installed, and dispatches here by task queue. A
    worker that also served workflows would blur which side owns orchestration.

    Asserted from the arguments actually handed to `Worker`, not from the source text: an
    earlier version of this test grepped for "workflows=" and matched the comment
    explaining its absence.
    """
    import asyncio

    from geneweaver.tools.temporal import worker as worker_module

    captured: dict = {}

    class _StubWorker:
        def __init__(self, client, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            raise _Stop  # stop `run` once the worker is built

        async def __aexit__(self, *_):
            return False

    class _Stop(Exception):
        pass

    async def _connect(*_args, **_kwargs):
        return object()

    monkeypatch.setenv("GENEWEAVER_TOOLS_PROFILE", "python")
    monkeypatch.setattr(worker_module, "Worker", _StubWorker)
    monkeypatch.setattr(worker_module.Client, "connect", _connect)

    with contextlib.suppress(_Stop):
        asyncio.run(worker_module.run())

    assert "activities" in captured, "the worker must register the tool activity"
    assert captured["activities"], "activity list is empty"
    assert "workflows" not in captured, (
        "the worker registered workflows; orchestration is AsyncTask's, not ours"
    )
    # A synchronous activity needs an executor, or Temporal refuses to build the worker.
    assert captured.get("activity_executor") is not None
