"""Which worker runs which tool, and on which task queue.

The nine tools split into exactly two dependency profiles, and that split -- not the tool
count -- is what the deployment mirrors:

* **python** -- seven tools that need only wheels (`scipy`/`scikit-learn` for DBSCAN's
  in-process default and JaccardClustering). No apt packages, no compilation.
* **native** -- MSET and PhenomeMap, which shell out to TOOLBOX binaries (`MSETcpp` needs
  OpenMP, `bstrap` needs Boost) and so need a build toolchain in their image.

One image per tool would produce seven near-identical images with nothing to isolate;
`asynctask-mpd-plugin` makes the same trade, running four analyses from three base images
with `anova` and `gxl` sharing one. Grouping by dependency profile also keeps MSET's Monte
Carlo sampling and PhenomeMap's biclique enumeration -- the two slow tools -- off the worker
serving fast interactive runs.

Task queue names come from the environment so the same image can serve a differently named
queue per cluster. They are resolved once at import, which makes them constant for the life
of a worker process: a workflow that scheduled an activity on one queue must schedule it on
the same queue when its history is replayed, so every pod sharing a deployment must share
this configuration (as it does, via one ConfigMap).
"""

import os

#: Tools whose runtime needs a compiled TOOLBOX binary. Everything else is pure Python.
#: DBSCAN is **not** here: its in-process implementation is the default and the binary is
#: only the legacy-parity fallback, so it belongs with the Python tools.
NATIVE_TOOLS: frozenset[str] = frozenset({"mset", "phenome_map"})

PYTHON_PROFILE = "python"
NATIVE_PROFILE = "native"
PROFILES = (PYTHON_PROFILE, NATIVE_PROFILE)

#: Selects what a worker serves and which queue it consumes. Set per deployment.
PROFILE_ENV_VAR = "GENEWEAVER_TOOLS_PROFILE"

#: Overrides the queue names, per the repository rule that infrastructure is configuration.
PYTHON_QUEUE_ENV_VAR = "GENEWEAVER_TOOLS_TASK_QUEUE"
NATIVE_QUEUE_ENV_VAR = "GENEWEAVER_TOOLS_NATIVE_TASK_QUEUE"

DEFAULT_PYTHON_QUEUE = "geneweaver-tools"
DEFAULT_NATIVE_QUEUE = "geneweaver-tools-native"

PYTHON_TASK_QUEUE = os.environ.get(PYTHON_QUEUE_ENV_VAR) or DEFAULT_PYTHON_QUEUE
NATIVE_TASK_QUEUE = os.environ.get(NATIVE_QUEUE_ENV_VAR) or DEFAULT_NATIVE_QUEUE


def task_queue_for(tool: str) -> str:
    """The queue whose worker can actually run `tool`.

    Called from workflow code to route the activity, so it must stay pure.
    """
    return NATIVE_TASK_QUEUE if tool in NATIVE_TOOLS else PYTHON_TASK_QUEUE


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
            "the routing in GeneWeaverToolWorkflow and that the target worker is deployed."
        )
