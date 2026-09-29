"""Temporal activity that executes a GeneWeaver analysis tool.

Tool runs are CPU-bound and some shell out to native binaries, neither of which is
permissible in Temporal workflow code -- workflows must be deterministic and replayable.
So the work happens here, in an activity, and the workflow only orchestrates.

One generic activity serves every tool rather than one per tool. The tools all satisfy
``AbstractTool.run(ToolInput) -> ToolOutput``; the only per-tool difference is the input
schema, which each tool declares and which is used to validate the request.
"""

import importlib.metadata
from typing import Any

from geneweaver.tools.framework.binary import progress_hook
from geneweaver.tools.temporal.payload import check_payload_size, check_tool_allowed
from geneweaver.tools.temporal.routing import check_tool_served_here
from temporalio import activity

#: Our own registry of runnable tools, distinct from the `jax.ats.plugins` group that
#: AsyncTask reads. Keeping them separate means AsyncTask is only ever offered the
#: workflow, never a bare compute class it cannot start.
TOOL_ENTRY_POINT_GROUP = "geneweaver.tools"


def available_tools() -> list[str]:
    """Names of every registered tool, for error messages and callers listing options."""
    return sorted(ep.name for ep in importlib.metadata.entry_points(group=TOOL_ENTRY_POINT_GROUP))


def load_tool(name: str) -> Any:
    """Resolve a registered tool by name.

    :param name: Registered tool name, e.g. ``upset``.
    :raises LookupError: If no tool is registered under that name.
    """
    for entry_point in importlib.metadata.entry_points(group=TOOL_ENTRY_POINT_GROUP):
        if entry_point.name == name:
            return entry_point.load()()
    raise LookupError(
        f"No GeneWeaver tool registered as {name!r}. Available: {available_tools() or 'none'}."
    )


def _cancellation_requested() -> bool:
    """Heartbeat, and report whether Temporal has asked for this activity to stop.

    Heartbeating is what makes cancellation observable at all: Temporal delivers it to the
    activity context, and an activity that never heartbeats never learns of it.
    """
    activity.heartbeat()
    return activity.is_cancelled()


#: Activity names share one flat namespace across every installed plugin:
#: `asynctask.plugins.temporal.discover_activity_plugins()` collects them with no dedup, and
#: Temporal's `Worker` raises `ValueError("More than one activity named ...")` at startup --
#: which would take down strain-recommendation and the MPD plugins with us. So the name is
#: explicit and prefixed, as `asynctask-mpd-plugin` does (`mpd_effects_download_drs_input`),
#: rather than defaulting to the bare function name `run_tool`.
ACTIVITY_NAME = "geneweaver_run_tool"


@activity.defn(name=ACTIVITY_NAME)
def run_tool(input_data: dict) -> dict:
    """Run one GeneWeaver tool and return its output as JSON-able primitives.

    :param input_data: ``{"tool": "upset", "input": {...}}``. The input is validated by the
        tool's own schema, so a malformed payload fails here with a pydantic error
        rather than deep inside the tool.
    :return: The tool's output, dumped to primitives for Temporal to serialise.
    :raises ValueError: If the tool is not cleared for AsyncTask execution, or its payload
        is too large for a Temporal argument.
    """
    name = input_data["tool"]

    # Defense in depth. The submission path and the workflow both check these first, because
    # by this point the payload has already crossed two boundaries Temporal could have
    # refused -- a check only here would never be reached for a genuinely oversized request.
    # Policy before size, so a blocked tool says why rather than reporting a size that
    # happens to fit.
    check_tool_allowed(name)
    size = check_payload_size(input_data)

    # All nine tools are registered by one distribution, so this image advertises tools it
    # may have no binary for. Refuse them by profile rather than letting the tool fail deep
    # inside with a missing-binary error that says nothing about which worker ran it.
    check_tool_served_here(name)

    tool = load_tool(name)
    tool_input = tool.tool_input(**input_data.get("input", {}))
    activity.logger.info("Running GeneWeaver tool %s (payload %d bytes)", name, size)

    # Lets a native binary heartbeat and observe cancellation from inside the tool, which
    # knows nothing about Temporal. Without it a cancelled run keeps this worker thread and
    # its child process alive until the subprocess bound expires.
    with progress_hook(_cancellation_requested):
        return tool.run(tool_input).model_dump(mode="json")
