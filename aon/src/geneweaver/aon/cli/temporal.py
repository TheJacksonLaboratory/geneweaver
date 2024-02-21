"""Commands for working with temporal jobs."""

from asyncio import run as aiorun
from datetime import timedelta

import typer
from geneweaver.aon.core.config import config
from geneweaver.aon.temporal import worker
from geneweaver.aon.temporal.load_data_workflow import GeneWeaverAonDataLoad
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleSpec,
)
from temporalio.service import RPCError

cli = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


async def _clear_schedules():
    """Clear all schedules."""
    try:
        client = await Client.connect(
            config.TEMPORAL_URI, namespace=config.TEMPORAL_NAMESPACE
        )
        handle = client.get_schedule_handle(
            "geneweaver-aon-agr-load-schedule",
        )

        await handle.delete()
    except RPCError:
        typer.echo("No Schedule to delete.")
        typer.Exit(0)


@cli.command()
def clear_schedules():
    """Clear all schedules."""
    aiorun(_clear_schedules())


async def _schedule_load(hour_frequency: int = 24):
    """Schedule a load job."""
    await _clear_schedules()
    client = await Client.connect(
        config.TEMPORAL_URI, namespace=config.TEMPORAL_NAMESPACE
    )
    await client.create_schedule(
        "geneweaver-aon-agr-load-schedule",
        Schedule(
            action=ScheduleActionStartWorkflow(
                GeneWeaverAonDataLoad.run,
                id="geneweaver-aon-agr-load-workflow",
                task_queue=config.TEMPORAL_TASK_QUEUE,
            ),
            spec=ScheduleSpec(
                intervals=[ScheduleIntervalSpec(every=timedelta(hours=hour_frequency))]
            ),
        ),
    )


@cli.command()
def schedule_load(hour_frequency: int = 24):
    """Schedule a load job."""
    aiorun(_schedule_load(hour_frequency))


async def _start_load():
    """Start a load job."""
    client = await Client.connect(
        config.TEMPORAL_URI, namespace=config.TEMPORAL_NAMESPACE
    )
    await client.start_workflow(
        GeneWeaverAonDataLoad.run,
        id="geneweaver-aon-agr-load-workflow",
        task_queue=config.TEMPORAL_TASK_QUEUE,
    )


@cli.command()
def start_load():
    """Start a load job."""
    aiorun(_start_load())


async def _cancel_load():
    """Cancel a load job."""
    client = await Client.connect(
        config.TEMPORAL_URI, namespace=config.TEMPORAL_NAMESPACE
    )
    await client.get_workflow_handle("geneweaver-aon-agr-load-workflow").cancel()


@cli.command()
def cancel_load():
    """Cancel a load job."""
    aiorun(_cancel_load())


async def _terminate_load():
    """Cancel a load job."""
    client = await Client.connect(
        config.TEMPORAL_URI, namespace=config.TEMPORAL_NAMESPACE
    )
    await client.get_workflow_handle("geneweaver-aon-agr-load-workflow").terminate()


@cli.command()
def terminate_load():
    """Cancel a load job."""
    aiorun(_terminate_load())


@cli.command()
def start_worker():
    aiorun(worker.main())
