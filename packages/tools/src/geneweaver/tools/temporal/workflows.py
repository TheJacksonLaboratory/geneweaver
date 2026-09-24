"""Temporal workflow wrapping a GeneWeaver tool run.

Thin by design: it delegates straight to the activity, which does the work. What lives
here is policy -- timeouts, retries, cancellation -- where it is visible, rather than
buried inside a tool.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import run_tool

#: Legacy's Celery worker used a 900s soft limit. Tool runs are minutes at worst; a
#: generous ceiling still beats a run that hangs forever (cf. G3-739, where failed runs
#: span indefinitely because nothing marked them failed).
TOOL_RUN_TIMEOUT = timedelta(minutes=30)


@workflow.defn
class GeneWeaverToolWorkflow:
    """Run a single GeneWeaver analysis tool."""

    @workflow.run
    async def run(self, request: dict) -> dict:
        """Execute the requested tool and return its output.

        Retries are disabled deliberately. A tool run is expensive and fully determined
        by its request, so retrying repeats the whole computation for no benefit;
        failures here are bad input or a missing binary, neither of which a retry fixes.
        """
        return await workflow.execute_activity(
            run_tool,
            request,
            start_to_close_timeout=TOOL_RUN_TIMEOUT,
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
