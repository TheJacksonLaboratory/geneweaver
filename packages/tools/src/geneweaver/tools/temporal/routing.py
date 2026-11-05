"""Which of the two workers this process is, and which tools it will run.

The queue names and which tools are native are the plugin's (`geneweaver.tools_plugin.contract`),
shared with the workflow that routes to them. What lives here is the worker-only half: this
worker's profile, read from its deployment, and the refusal of a tool that belongs to the
other worker.
"""

import os

from geneweaver.tools_plugin.contract import (
    NATIVE_TASK_QUEUE,
    NATIVE_TOOLS,
    PYTHON_TASK_QUEUE,
    task_queue_for,
)

PYTHON_PROFILE = "python"
NATIVE_PROFILE = "native"
PROFILES = (PYTHON_PROFILE, NATIVE_PROFILE)

#: Selects what a worker serves and which queue it consumes. Set per deployment.
PROFILE_ENV_VAR = "GENEWEAVER_TOOLS_PROFILE"

#: The task queue each profile consumes: the plugin's names, so the worker listens where the
#: workflow sends.
QUEUE_FOR_PROFILE = {PYTHON_PROFILE: PYTHON_TASK_QUEUE, NATIVE_PROFILE: NATIVE_TASK_QUEUE}


def profile_for(tool: str) -> str:
    """Which worker profile serves `tool`."""
    return NATIVE_PROFILE if tool in NATIVE_TOOLS else PYTHON_PROFILE


def current_profile() -> str:
    """This worker's profile.

    :raises ValueError: If unset or unrecognised. Deliberately fatal rather than defaulted:
        a worker that guessed `python` would advertise MSET and PhenomeMap and fail every
        run with a missing-binary error, which is far harder to diagnose than a worker that
        refuses to start.
    """
    profile = os.environ.get(PROFILE_ENV_VAR, "").strip().lower()
    if profile not in PROFILES:
        raise ValueError(
            f"{PROFILE_ENV_VAR} must be one of {', '.join(PROFILES)}; got {profile!r}. "
            "It decides which tools this worker serves and which task queue it consumes."
        )
    return profile


def tools_for_profile(profile: str, available: list[str]) -> list[str]:
    """The subset of `available` that `profile` is allowed to run.

    All nine tools are registered by the single `geneweaver-tools` distribution, so an image
    without the TOOLBOX binaries still advertises MSET and PhenomeMap through its entry
    points. Enablement therefore cannot be inferred from what is installed -- it has to be
    declared, which is what the profile does.
    """
    if profile == NATIVE_PROFILE:
        return sorted(name for name in available if name in NATIVE_TOOLS)
    return sorted(name for name in available if name not in NATIVE_TOOLS)


def check_tool_served_here(tool: str, profile: str | None = None) -> None:
    """Refuse a tool this worker is not the right one to run.

    A misrouted tool would otherwise fail deep inside the tool with a missing-binary error
    that says nothing about queues.

    :raises ValueError: If `tool` belongs to a different profile.
    """
    here = current_profile() if profile is None else profile
    wanted = profile_for(tool)
    if wanted != here:
        raise ValueError(
            f"{tool} is served by the {wanted!r} worker profile, but this worker is "
            f"{here!r}. It should have been scheduled on {task_queue_for(tool)!r}; check "
            "the routing in geneweaver-tools-plugin and that the target worker is deployed."
        )
