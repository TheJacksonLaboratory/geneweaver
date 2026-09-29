"""Temporal worker for the GeneWeaver tools.

Runs the tool compute in GeneWeaver's own image on GeneWeaver's own task queue, rather than
inside AsyncTask's shared worker. `asynctask-mpd-plugin` is the precedent: its plugin
workflow orchestrates on AsyncTask's queue, then dispatches the heavy activity with
`task_queue="mpd-effects"` to workers running an image that has R installed.

Three things follow from that, all of which the in-AsyncTask arrangement could not give:

* The TOOLBOX binaries ship in *our* image. AsyncTask's image has no build toolchain, and
  adding one is a change to a repository this team does not own.
* Tool runs stop competing for AsyncTask's shared activity thread pool with
  strain-recommendation and the MPD analyses.
* Concurrency, resources and scaling are set per profile -- MSET's Monte Carlo sampling
  does not have to share a pod with fast interactive UpSet runs.

Two deployments run this module, distinguished only by `GENEWEAVER_TOOLS_PROFILE`; see
`routing.py` for why the split is by dependency profile rather than per tool.
"""

import asyncio
import logging
import os

from geneweaver.tools.temporal import ACTIVITIES, WORKFLOWS
from geneweaver.tools.temporal.activities import available_tools
from geneweaver.tools.temporal.routing import (
    NATIVE_PROFILE,
    NATIVE_TASK_QUEUE,
    PYTHON_TASK_QUEUE,
    current_profile,
    tools_for_profile,
)
from temporalio.client import Client
from temporalio.worker import Worker

logger = logging.getLogger(__name__)

#: Temporal connection. Named to match AsyncTask's own worker configuration so one
#: ConfigMap can serve both.
TEMPORAL_URI_ENV_VAR = "TEMPORAL_URI"
TEMPORAL_NAMESPACE_ENV_VAR = "TEMPORAL_NAMESPACE"

DEFAULT_TEMPORAL_URI = "localhost:7233"
DEFAULT_TEMPORAL_NAMESPACE = "default"

#: Activities are synchronous and CPU-bound, so this caps concurrent tool runs per pod.
#: Low by default and low on purpose: a tool run can saturate a core for minutes, and
#: `asynctask-mpd-plugin` settled on 5 for the same reason. Scale out with replicas.
MAX_CONCURRENT_ENV_VAR = "MAX_CONCURRENT_ACTIVITIES"
DEFAULT_MAX_CONCURRENT_ACTIVITIES = 5


def max_concurrent_activities() -> int:
    """Per-pod concurrency, falling back rather than failing on a bad value."""
    raw = os.environ.get(MAX_CONCURRENT_ENV_VAR)
    if not raw:
        return DEFAULT_MAX_CONCURRENT_ACTIVITIES
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "%s=%r is not an integer; using %d",
            MAX_CONCURRENT_ENV_VAR,
            raw,
            DEFAULT_MAX_CONCURRENT_ACTIVITIES,
        )
        return DEFAULT_MAX_CONCURRENT_ACTIVITIES
    if value < 1:
        logger.warning(
            "%s=%d is not usable; using %d",
            MAX_CONCURRENT_ENV_VAR,
            value,
            DEFAULT_MAX_CONCURRENT_ACTIVITIES,
        )
        return DEFAULT_MAX_CONCURRENT_ACTIVITIES
    return value


def task_queue(profile: str) -> str:
    """The queue this worker consumes, from its profile."""
    return NATIVE_TASK_QUEUE if profile == NATIVE_PROFILE else PYTHON_TASK_QUEUE


async def run() -> None:
    """Connect to Temporal and serve tool runs until the process is stopped."""
    # Resolved before connecting: an unset or misspelled profile is fatal, and it should be
    # fatal at startup rather than on the first run that reaches the wrong worker.
    profile = current_profile()
    queue = task_queue(profile)
    served = tools_for_profile(profile, available_tools())

    uri = os.environ.get(TEMPORAL_URI_ENV_VAR) or DEFAULT_TEMPORAL_URI
    namespace = os.environ.get(TEMPORAL_NAMESPACE_ENV_VAR) or DEFAULT_TEMPORAL_NAMESPACE

    logger.info(
        "Starting GeneWeaver tools worker: profile=%s queue=%s namespace=%s temporal=%s",
        profile,
        queue,
        namespace,
        uri,
    )
    # Logged because "the run never started" is otherwise indistinguishable from "this
    # worker does not serve that tool": the queue a task went to is not visible from here.
    logger.info("Serving tools: %s", ", ".join(served) or "none")

    client = await Client.connect(uri, namespace=namespace)

    # Activities run in a thread pool: they are synchronous and CPU-bound, and some block
    # in a subprocess. `framework.binary` polls rather than blocking so cancellation is
    # still delivered.
    async with Worker(
        client,
        task_queue=queue,
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
        max_concurrent_activities=max_concurrent_activities(),
    ):
        await asyncio.Future()


def main() -> None:
    """Console entry point."""
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
