"""Test the scheduled AGR load (G3-837)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from geneweaver.aon.core.config_class import Config
from geneweaver.aon.temporal import schedule
from temporalio.client import ScheduleAlreadyRunningError, ScheduleOverlapPolicy
from temporalio.service import RPCError, RPCStatusCode


def test_every_environment_loads_monthly_by_default() -> None:
    """06:00 UTC on the 1st, unless an environment's configmap says otherwise."""
    assert Config().LOAD_SCHEDULE_CRON == "0 6 1 * *"


def test_the_schedule_runs_the_load_on_the_cron_and_never_overlaps() -> None:
    """One load at a time, started as the load workflow."""
    s = schedule.load_schedule(cron="0 6 1 * *")
    assert list(s.spec.cron_expressions) == ["0 6 1 * *"]
    assert not s.spec.intervals
    assert s.policy.overlap == ScheduleOverlapPolicy.SKIP
    assert s.action.id == schedule.WORKFLOW_ID


def test_hour_frequency_still_schedules_an_interval() -> None:
    """`schedule-load --hour-frequency` keeps working."""
    s = schedule.load_schedule(hour_frequency=24)
    assert s.spec.intervals[0].every.total_seconds() == 24 * 3600
    assert not s.spec.cron_expressions


def _client() -> MagicMock:
    client = MagicMock()
    client.create_schedule = AsyncMock()
    client.get_schedule_handle.return_value.update = AsyncMock()
    return client


def test_an_existing_schedule_is_replaced() -> None:
    """Each deploy restarts the worker; a schedule from the last one is updated."""
    client = _client()
    client.create_schedule.side_effect = ScheduleAlreadyRunningError()
    new = schedule.load_schedule(cron="0 6 1 * *")
    asyncio.run(schedule.set_load_schedule(client, new))
    updater = client.get_schedule_handle.return_value.update.call_args.args[0]
    assert updater(None).schedule is new


def test_the_worker_sets_the_configured_schedule() -> None:
    """The worker schedules LOAD_SCHEDULE_CRON when it starts."""
    client = _client()
    with patch.object(schedule.config, "LOAD_SCHEDULE_CRON", "0 6 1 * *"):
        asyncio.run(schedule.ensure_load_schedule(client))
    created = client.create_schedule.call_args.args
    assert created[0] == schedule.SCHEDULE_ID
    assert list(created[1].spec.cron_expressions) == ["0 6 1 * *"]


def test_an_empty_setting_leaves_the_schedule_alone() -> None:
    """An environment can opt out without deleting a schedule set by hand."""
    client = _client()
    with patch.object(schedule.config, "LOAD_SCHEDULE_CRON", ""):
        asyncio.run(schedule.ensure_load_schedule(client))
    client.create_schedule.assert_not_called()


def test_a_temporal_error_does_not_stop_the_worker() -> None:
    """Loads started by hand must still run if the schedule cannot be set."""
    client = _client()
    client.create_schedule.side_effect = RPCError(
        "invalid cron", RPCStatusCode.INVALID_ARGUMENT, b""
    )
    with patch.object(schedule.config, "LOAD_SCHEDULE_CRON", "not a cron"):
        asyncio.run(schedule.ensure_load_schedule(client))
