"""Temporal workflow wrapping a GeneWeaver tool run.

Thin by design: it delegates straight to the activity, which does the work. What lives
here is policy -- timeouts, retries, cancellation -- where it is visible, rather than
buried inside a tool.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from geneweaver.tools.framework.binary import TOOL_RUN_TIMEOUT_SECONDS

    from .activities import run_tool
    from .payload import check_payload_size, check_tool_allowed

#: Legacy's Celery worker used a 900s soft limit. Tool runs are minutes at worst; a
#: generous ceiling still beats a run that hangs forever (cf. G3-739, where failed runs
#: span indefinitely because nothing marked them failed).
#:
#: Defined in `framework.binary` so the subprocess bound can be capped against it without
#: that module importing temporalio; `test_the_activity_deadline_is_the_one_binary_py_caps_against`
#: pins them together.
TOOL_RUN_TIMEOUT = timedelta(seconds=TOOL_RUN_TIMEOUT_SECONDS)

#: Without this, heartbeating buys nothing: Temporal only delivers cancellation to an
#: activity that heartbeats, and only treats a missed heartbeat as a failure when a heartbeat
#: timeout is set. Comfortably above `binary.POLL_INTERVAL_SECONDS`, so an ordinary run is
#: never declared dead for being briefly busy.
TOOL_HEARTBEAT_TIMEOUT = timedelta(seconds=60)


@workflow.defn
class GeneWeaverToolWorkflow:
    """Run a single GeneWeaver analysis tool."""

    @workflow.run
    async def run(self, input_data: dict) -> dict:
        """Execute the requested tool and return its output.

        The parameter **must** be named ``input_data``. AsyncTask's plugin facade does
        `inspect.signature(plugin.run).parameters["input_data"]` in `validate_schemas`,
        and `load_plugins()` catches the resulting `ValueError` and silently omits the
        plugin from its registry -- so a different name means the tools are never
        discovered, with only a warning in the service's log. Both precedents
        (`StrainRecommendWorkflow`, `DRSTestWorkflow`) use the same name.

        Annotations on the parameter and the return are required for the same reason:
        `validate_schemas` rejects `inspect.Parameter.empty` for either.

        `dict` rather than a pydantic model: AsyncTask installs its own data converter,
        so a plain mapping is the payload shape that needs no assumptions about it. The
        activity validates against the tool's own input schema, which is where the real
        contract lives.

        Retries are disabled deliberately. A tool run is expensive and fully determined
        by its request, so retrying repeats the whole computation for no benefit;
        failures here are bad input or a missing binary, neither of which a retry fixes.
        """
        # Checked here, not only in the activity: by the time the activity runs the payload
        # has already crossed into workflow input and an activity argument, either of which
        # Temporal could have refused first -- so the attributable error would never be
        # reached. Both checks are pure and deterministic, so they are replay-safe.
        check_tool_allowed(input_data["tool"])
        check_payload_size(input_data)

        return await workflow.execute_activity(
            run_tool,
            input_data,
            start_to_close_timeout=TOOL_RUN_TIMEOUT,
            heartbeat_timeout=TOOL_HEARTBEAT_TIMEOUT,
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
