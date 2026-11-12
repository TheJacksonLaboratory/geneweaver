"""The scheduled AGR load (G3-837).

Loads were only ever started by hand: `gwaon temporal schedule-load` existed, but
nothing called it, so no environment loaded an AGR release after February 2024. The
worker now sets the schedule from ``LOAD_SCHEDULE_CRON`` each time it starts, so
every environment's deploy applies it. A run for a release that is already loaded
stops before writing anything.
"""

from datetime import timedelta
from typing import Optional

from geneweaver.aon.core.config import config
from geneweaver.aon.temporal.load_data_workflow import GeneWeaverAonDataLoad
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleUpdate,
)
from temporalio.service import RPCError

SCHEDULE_ID = "geneweaver-aon-agr-load-schedule"
WORKFLOW_ID = "geneweaver-aon-agr-load-workflow"
MONTHLY = "0 6 1 * *"


def load_schedule(
    cron: Optional[str] = None, hour_frequency: Optional[int] = None
) -> Schedule:
    """Return the AGR load schedule.

    :param cron: A cron expression, in UTC.
    :param hour_frequency: Hours between loads, used instead of ``cron``.
    :return: The schedule.
    """
    if hour_frequency is not None:
        spec = ScheduleSpec(
            intervals=[ScheduleIntervalSpec(every=timedelta(hours=hour_frequency))]
        )
    else:
        spec = ScheduleSpec(cron_expressions=[cron or MONTHLY])
    return Schedule(
        action=ScheduleActionStartWorkflow(
            GeneWeaverAonDataLoad.run,
            id=WORKFLOW_ID,
            task_queue=config.TEMPORAL_TASK_QUEUE,
        ),
        spec=spec,
        # Temporal's default, stated: a load can take longer than the interval,
        # and two loads of one release must not run at once (G3-837).
        policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
    )


async def set_load_schedule(client: Client, schedule: Schedule) -> None:
    """Create the AGR load schedule, or replace it if it exists.

    :param client: A Temporal client in the environment's namespace.
    :param schedule: The schedule to set.
    """
    try:
        await client.create_schedule(SCHEDULE_ID, schedule)
    except ScheduleAlreadyRunningError:
        await client.get_schedule_handle(SCHEDULE_ID).update(
            lambda _: ScheduleUpdate(schedule=schedule)
        )


async def ensure_load_schedule(client: Client) -> None:
    """Set the schedule from ``LOAD_SCHEDULE_CRON`` when the worker starts.

    An empty value leaves the schedule as it is. A failure is reported but does not
    stop the worker: loads started by hand must still run.

    :param client: A Temporal client in the environment's namespace.
    """
    cron = config.LOAD_SCHEDULE_CRON
    if not cron:
        print("LOAD_SCHEDULE_CRON is empty; the AGR load schedule is left as is.")
        return
    try:
        await set_load_schedule(client, load_schedule(cron=cron))
    except RPCError as e:
        print(f"Could not set the AGR load schedule ({cron!r}): {e}", flush=True)
        return
    print(f"AGR load scheduled: {cron!r} (UTC).", flush=True)
