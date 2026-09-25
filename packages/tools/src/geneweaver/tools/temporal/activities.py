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


@activity.defn
def run_tool(request: dict) -> dict:
    """Run one GeneWeaver tool and return its output as JSON-able primitives.

    :param request: ``{"tool": "upset", "input": {...}}``. The input is validated by the
        tool's own schema, so a malformed payload fails here with a pydantic error
        rather than deep inside the tool.
    :return: The tool's output, dumped to primitives for Temporal to serialise.
    """
    tool = load_tool(request["tool"])
    tool_input = tool.tool_input(**request.get("input", {}))
    activity.logger.info("Running GeneWeaver tool %s", request["tool"])
    return tool.run(tool_input).model_dump(mode="json")
