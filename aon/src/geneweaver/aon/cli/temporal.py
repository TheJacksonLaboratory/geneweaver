"""Commands for working with temporal jobs."""

from asyncio import run as aiorun
from typing import Optional

import typer
from geneweaver.aon.core.config import config
from geneweaver.aon.temporal import worker
from geneweaver.aon.temporal.load_data_workflow import GeneWeaverAonDataLoad
from geneweaver.aon.temporal.schedule import (
    SCHEDULE_ID,
    WORKFLOW_ID,
    load_schedule,
    set_load_schedule,
)
from temporalio.client import Client
from temporalio.service import RPCError

cli = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


async def _clear_schedules() -> None:
    """Clear all schedules."""
    try:
        client = await Client.connect(
            config.TEMPORAL_URI, namespace=config.TEMPORAL_NAMESPACE
        )
        handle = client.get_schedule_handle(
            SCHEDULE_ID,
        )

        await handle.delete()
    except RPCError:
        typer.echo("No Schedule to delete.")
        typer.Exit(0)


@cli.command()
def clear_schedules() -> None:
    """Clear all schedules."""
    aiorun(_clear_schedules())


async def _schedule_load(
    cron: Optional[str] = None, hour_frequency: Optional[int] = None
) -> None:
    """Schedule a load job."""
    client = await Client.connect(
        config.TEMPORAL_URI, namespace=config.TEMPORAL_NAMESPACE
    )
    await set_load_schedule(
        client,
        load_schedule(
            cron=cron or config.LOAD_SCHEDULE_CRON, hour_frequency=hour_frequency
        ),
    )


@cli.command()
def schedule_load(
    cron: Optional[str] = None, hour_frequency: Optional[int] = None
) -> None:
    """Schedule the AGR load: by cron (UTC; default LOAD_SCHEDULE_CRON, monthly).

    Pass --hour-frequency to run every N hours instead. The worker also sets the
    schedule from LOAD_SCHEDULE_CRON each time it starts.
    """
    aiorun(_schedule_load(cron, hour_frequency))


async def _start_load() -> None:
    """Start a load job."""
    client = await Client.connect(
        config.TEMPORAL_URI, namespace=config.TEMPORAL_NAMESPACE
    )
    await client.start_workflow(
        GeneWeaverAonDataLoad.run,
        id=WORKFLOW_ID,
        task_queue=config.TEMPORAL_TASK_QUEUE,
    )


@cli.command()
def start_load() -> None:
    """Start a load job."""
    aiorun(_start_load())


async def _cancel_load() -> None:
    """Cancel a load job."""
    client = await Client.connect(
        config.TEMPORAL_URI, namespace=config.TEMPORAL_NAMESPACE
    )
    await client.get_workflow_handle(WORKFLOW_ID).cancel()


@cli.command()
def cancel_load() -> None:
    """Cancel a load job."""
    aiorun(_cancel_load())


async def _terminate_load() -> None:
    """Cancel a load job."""
    client = await Client.connect(
        config.TEMPORAL_URI, namespace=config.TEMPORAL_NAMESPACE
    )
    await client.get_workflow_handle(WORKFLOW_ID).terminate()


@cli.command()
def terminate_load() -> None:
    """Cancel a load job."""
    aiorun(_terminate_load())


@cli.command()
def start_worker() -> None:
    """Start the worker."""
    aiorun(worker.main())
