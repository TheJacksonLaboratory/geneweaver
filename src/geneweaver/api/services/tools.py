"""Service functions for running the ported analysis tools.

The flow is the same for every tool and worth keeping that way as more are added:

1. **gate** -- confirm the caller may read every gene set they named;
2. **resolve** -- turn gene set ids into the tool's input (`geneweaver.db.tool_input`);
3. **run** -- on AsyncTask when it is configured and the caller is signed in, otherwise
   in-process through a `ToolRunner`;
4. **shape** -- map the tool's output onto the API schema.

**Where a run executes.** AsyncTask runs every tool, including MSET and PhenomeMap, whose
native binaries only its worker images carry. It runs as the user (`services.asynctask`), so
an anonymous caller cannot use it: they keep the in-process path for the seven pure-Python
tools, exactly as before, and are asked to sign in for the two native ones. With
`ASYNCTASK_API_URL` unset -- every environment but dev today -- nothing changes at all.

Step 1 is the security-relevant one. The tools themselves know nothing about users, so a
missing gate here means a caller could read gene sets through a tool result that they
could not read directly. `db_geneset.is_readable` is the same check the gene set
endpoints use, with user id 0 standing for anonymous.
"""

import importlib.metadata
from collections.abc import Callable
from typing import Any

from geneweaver.db import geneset as db_geneset
from geneweaver.db import tool_input as db_tool_input
from geneweaver.tools.upset import UpSet, UpSetInput
from psycopg import Cursor

from geneweaver.api.core.config import settings
from geneweaver.api.core.exceptions import UnauthorizedException
from geneweaver.api.schemas.auth import User
from geneweaver.api.schemas.tools import UpSetIntersection, UpSetResult
from geneweaver.api.services import tool_inputs
from geneweaver.api.services.asynctask import COMPLETED, AsyncTaskClient
from geneweaver.api.services.geneset import determine_user_id
from geneweaver.api.services.tool_runner import InProcessToolRunner, ToolRunner


class UnknownToolError(LookupError):
    """Raised when no tool is registered under the requested name.

    A subclass of LookupError for backwards compatibility, but a *distinct* type on
    purpose: `IndexError` and `KeyError` are also LookupErrors, so catching the base class
    at the endpoint reported a bug inside a tool as "no such tool" with a 404.
    """


#: Registry the tools are loaded from -- the same group the Temporal activity dispatches
#: against, so the API and the worker can never disagree about what a tool name means.
TOOL_ENTRY_POINT_GROUP = "geneweaver.tools"

#: Tools that cannot run inside the API process, and why. Both shell out to a compiled
#: TOOLBOX binary, and the API image deliberately carries none: the binaries live in
#: `geneweaver-tools-native-worker`, which reaches them through AsyncTask. Listing them
#: here rather than omitting them means a request gets an explanation instead of a
#: missing-binary stack trace.
IN_PROCESS_UNAVAILABLE: dict[str, str] = {
    "mset": (
        "MSET needs the MSETcpp binary, which is not in the API image. It runs on the "
        "geneweaver-tools-native-worker via AsyncTask (G3-750)."
    ),
    "phenome_map": (
        "PhenomeMap needs the biclique and bstrap binaries, which are not in the API "
        "image. It runs on the geneweaver-tools-native-worker via AsyncTask (G3-750)."
    ),
}

#: Caveats that do not stop a run but change how the result should be read. Returned with
#: the result rather than buried in a docstring, because a p-value computed from an empty
#: null distribution looks exactly like a real one.
TOOL_CAVEATS: dict[str, str] = {
    "jaccard_similarity": (
        "p-values depend on extsrc.jaccard_distribution_results, whose coverage is "
        "partial: a gene-set pair whose sizes have no matching distribution gets no "
        "p-value. The similarity values are unaffected. (The roadmap records this table "
        "as empty across local/dev/sqa; on dev it holds 2,731 rows covering 1,278 size "
        "pairs, so that claim is at least out of date there.)"
    ),
}


def _gate_geneset_access(cursor: Cursor, user: User | None, geneset_ids: list[int]) -> None:
    """Refuse the run unless every named gene set is readable by the caller.

    Anonymous callers resolve to user id 0, which `geneset_is_readable2` treats as the
    public audience -- so an anonymous run sees public gene sets and nothing else.

    :raises UnauthorizedException: if any gene set is not readable.
    """
    user_id = determine_user_id(user)
    unreadable = [
        geneset_id
        for geneset_id in geneset_ids
        if not db_geneset.is_readable(cursor, user_id, geneset_id)
    ]
    if unreadable:
        raise UnauthorizedException(
            detail=(
                "Not authorized to read gene set(s): "
                + ", ".join(str(geneset_id) for geneset_id in unreadable)
            )
        )


def run_upset(
    cursor: Cursor,
    geneset_ids: list[int],
    user: User | None = None,
    include_zeros: bool = False,
    runner: ToolRunner | None = None,
) -> UpSetResult:
    """Run UpSet over the given gene sets and return the exclusive intersection sizes.

    :param cursor: The database cursor.
    :param geneset_ids: The gene sets to intersect.
    :param user: The requesting user, or None for anonymous.
    :param include_zeros: Emit combinations with no genes.
    :param runner: Execution backend; defaults to running in-process.
    :return: The intersection sizes, largest first.
    :raises UnauthorizedException: If any gene set is not readable by the caller.
    """
    _gate_geneset_access(cursor, user, geneset_ids)

    memberships = db_tool_input.gene_symbols_by_geneset(cursor, geneset_ids)
    tool_input = UpSetInput(
        geneset_ids=[str(geneset_id) for geneset_id in geneset_ids],
        gene_memberships=memberships,
        include_zeros=include_zeros,
    )

    # The Analyze page's default tool comes through here rather than `run_tool`, so it
    # must route the same way or the most-used run would never reach AsyncTask.
    asynctask = asynctask_client_for(user)
    if asynctask is None:
        output = (runner or InProcessToolRunner()).run(UpSet(), tool_input)
        intersections = [(item.genesets, item.size) for item in output.intersections]
    else:
        envelope = {"tool": "upset", "input": tool_input.model_dump(mode="json")}
        ran = _run_on_asynctask(asynctask, envelope, "upset", geneset_ids)
        intersections = [
            (item["genesets"], item["size"]) for item in ran["result"]["intersections"]
        ]

    return UpSetResult(
        geneset_ids=geneset_ids,
        gene_counts={key: len(genes) for key, genes in memberships.items()},
        intersections=[
            UpSetIntersection(geneset_ids=genesets, size=size) for genesets, size in intersections
        ],
    )


def available_tools() -> list[str]:
    """Every registered tool name, whether or not the API can run it in-process."""
    return sorted(ep.name for ep in importlib.metadata.entry_points(group=TOOL_ENTRY_POINT_GROUP))


def load_tool(name: str) -> Any:
    """Resolve a registered tool by name.

    :raises UnknownToolError: If no tool is registered under that name.
    """
    for entry_point in importlib.metadata.entry_points(group=TOOL_ENTRY_POINT_GROUP):
        if entry_point.name == name:
            return entry_point.load()()
    raise UnknownToolError(f"No tool registered as {name!r}. Available: {available_tools()}.")


class ToolRequestError(Exception):
    """The request cannot be run as asked -- a 422, not a server conflict.

    Deliberately not a ValueError: the endpoint maps ValueError to 409 ("cannot run
    here"), which would tell the caller to wait for a deployment rather than fix the
    request.
    """


class SignInRequired(Exception):
    """The tool runs only on AsyncTask, which acts as a user, and the caller is anonymous."""


class ToolRunPending(Exception):
    """The run was accepted but had not finished within the wait; poll it by id."""

    def __init__(self, tool: str, geneset_ids: list[int], run_id: int, status: str) -> None:
        super().__init__(f"{tool} run {run_id} is still {status}.")
        self.body = {"tool": tool, "geneset_ids": geneset_ids, "run_id": run_id, "status": status}


class ToolRunFailed(Exception):
    """AsyncTask ran the tool and it did not complete.

    AsyncTask records only a status, never the cause, so the workflow id is carried to find
    the cause in Temporal.
    """


def asynctask_configured() -> bool:
    """Whether this environment sends tool runs to AsyncTask at all."""
    return bool(settings.ASYNCTASK_API_URL)


def asynctask_client_for(user: User | None) -> AsyncTaskClient | None:
    """An AsyncTask client acting as `user`, or None if runs stay in-process for them.

    None for an anonymous caller: AsyncTask authenticates every call and records an owner
    for every run, so there is no one to submit as.
    """
    token = getattr(user, "token", None)
    if not asynctask_configured() or not token:
        return None
    return AsyncTaskClient(
        settings.ASYNCTASK_API_URL,
        token,
        request_timeout=settings.ASYNCTASK_REQUEST_TIMEOUT_SECONDS,
    )


def _as_strings(geneset_ids: list[int]) -> list[str]:
    """Gene set ids as the tools label them."""
    return [str(geneset_id) for geneset_id in geneset_ids]


# --- per-tool input builders -------------------------------------------------------
#
# Each takes the cursor, the requested gene set ids, their already-resolved memberships,
# and the caller's parameters, and returns the keyword arguments for that tool's input
# model. Signatures are uniform so `run_tool` needs no per-tool branching.


def _upset_input(cursor, geneset_ids, memberships, parameters) -> dict:
    return {
        "geneset_ids": _as_strings(geneset_ids),
        "gene_memberships": memberships,
        "include_zeros": bool(parameters.get("include_zeros", False)),
    }


def _dbscan_input(cursor, geneset_ids, memberships, parameters) -> dict:
    # Defaults match the smallest case `validate_dbscan.py` exercises; anything larger
    # than (distinct genes - 1) makes the tool decline to run, which it reports as
    # `ran=False` rather than failing.
    return {
        "gene_symbols": memberships,
        "epsilon": int(parameters.get("epsilon", 1)),
        "min_points": int(parameters.get("min_points", 2)),
        "geneset_ids": _as_strings(geneset_ids),
    }


def _hypergeometric_input(cursor, geneset_ids, memberships, parameters) -> dict:
    return {
        "geneset_ids": _as_strings(geneset_ids),
        "pairs": tool_inputs.contingency_pairs(memberships, geneset_ids),
    }


def _jaccard_clustering_input(cursor, geneset_ids, memberships, parameters) -> dict:
    return {
        "geneset_ids": _as_strings(geneset_ids),
        "method": parameters.get("method", "average"),
        "similarity": tool_inputs.similarity_matrix(memberships, geneset_ids),
    }


def _jaccard_similarity_input(cursor, geneset_ids, memberships, parameters) -> dict:
    return {
        "geneset_ids": _as_strings(geneset_ids),
        "include_homology": bool(parameters.get("include_homology", False)),
        "p_value_threshold": float(parameters.get("p_value_threshold", 0.05)),
        "pairs": tool_inputs.jaccard_pair_counts(memberships, geneset_ids),
        "distributions": db_tool_input.jaccard_distributions(cursor),
    }


def _combine_input(cursor, geneset_ids, memberships, parameters) -> dict:
    include_homology = bool(parameters.get("include_homology", True))
    return {
        "geneset_ids": list(geneset_ids),
        "include_homology": include_homology,
        "membership_rows": db_tool_input.membership_rows(cursor, geneset_ids),
        # Only fetched when it will be used: the homology join is the expensive query here.
        "homology_pairs": (
            db_tool_input.homology_pairs(cursor, geneset_ids) if include_homology else []
        ),
        "label_rows": db_tool_input.geneset_labels(cursor, geneset_ids),
    }


def _boolean_algebra_input(cursor, geneset_ids, memberships, parameters) -> dict:
    species = db_tool_input.species_by_geneset(cursor, geneset_ids)
    # Distinct species, not one per gene set: the tool groups genes by species to decide
    # what can be identified across them, and a repeated species id would double-count.
    species_ids = sorted({species.get(geneset_id, 0) for geneset_id in geneset_ids})
    return {
        "relation": str(parameters.get("relation", "union")).lower(),
        "at_least": int(parameters.get("at_least", 2)),
        "geneset_ids": list(geneset_ids),
        "species_ids": species_ids,
        # `homolog_annotations`, not `homology_pairs`: this tool wants gene membership
        # annotated with Homologene groups (6 columns, NULLs included), which is a
        # different query. Passing the ortholog pairs instead returned no results at all
        # and raised IndexError on a cross-species request.
        "homolog_data": db_tool_input.homolog_annotations(cursor, geneset_ids, species_ids),
    }


#: Tool name -> input builder. A tool missing from here has no resolver yet and is
#: reported as such, rather than failing on a validation error from its own schema.
INPUT_BUILDERS: dict[str, Callable[..., dict]] = {
    "upset": _upset_input,
    "dbscan": _dbscan_input,
    "hypergeometric": _hypergeometric_input,
    "jaccard_clustering": _jaccard_clustering_input,
    "jaccard_similarity": _jaccard_similarity_input,
    "combine": _combine_input,
    "boolean_algebra": _boolean_algebra_input,
}


# --- AsyncTask-only builders ---------------------------------------------------------
#
# The native tools never run in this process, so these return the whole AsyncTask
# envelope rather than a tool input: MSET's must carry a universe *reference* beside the
# input, which its own schema has no field for.


def _mset_envelope(cursor, geneset_ids, memberships, parameters) -> dict:
    """Compare two gene sets against their species' full gene space.

    The background is sent as a reference the worker resolves from the database (G3-784),
    never inline: the universe is ~100,000 identifiers, at or over Temporal's 2 MiB limit.
    """
    if len(geneset_ids) != 2:
        raise ToolRequestError(
            f"MSET compares exactly two gene sets; {len(geneset_ids)} were given."
        )
    first, second = (str(geneset_id) for geneset_id in geneset_ids)
    tool_input = {
        "group_1_genes": memberships.get(first, []),
        "group_2_genes": memberships.get(second, []),
    }
    if "number_of_samples" in parameters:
        tool_input["number_of_samples"] = int(parameters["number_of_samples"])
    if "over_representation" in parameters:
        tool_input["over_representation"] = bool(parameters["over_representation"])
    return {
        "tool": "mset",
        "input": tool_input,
        "universe": {"geneset_ids": list(geneset_ids)},
    }


#: PhenomeMap options a caller may set; anything else is the tool's own default.
PHENOME_MAP_PARAMETERS = (
    "min_genes",
    "max_level",
    "p_value_threshold",
    "use_fdr",
    "disable_bootstrap",
    "bootstrap_node_threshold",
)


def _phenome_map_envelope(cursor, geneset_ids, memberships, parameters) -> dict:
    """The gene-set/gene bipartite graph, with no gene ranks.

    Without ranks the link score is the gene-count ratio alone, which the tool documents
    as supported; ranked scoring needs a ranking source v3 does not have yet.
    """
    tool_input = {"gene_sets": memberships}
    tool_input.update(
        {key: parameters[key] for key in PHENOME_MAP_PARAMETERS if key in parameters}
    )
    return {"tool": "phenome_map", "input": tool_input}


#: Tool name -> envelope builder, for tools that run only on AsyncTask.
ASYNCTASK_ONLY_BUILDERS: dict[str, Callable[..., dict]] = {
    "mset": _mset_envelope,
    "phenome_map": _phenome_map_envelope,
}

#: Shown with a native tool's availability once AsyncTask is configured, because the
#: picker is listed before anyone signs in.
SIGN_IN_CAVEAT = "Runs on AsyncTask, which requires signing in."


def tool_availability() -> dict[str, dict[str, Any]]:
    """What each registered tool's state is, for the UI's picker.

    Returned from the API rather than hardcoded in the front end so the two cannot drift:
    the page previously listed five of the nine tools, which made the port look narrower
    than it is.
    """
    on_asynctask = asynctask_configured()
    availability = {}
    for name in available_tools():
        reason = None
        caveat = TOOL_CAVEATS.get(name)
        if name in ASYNCTASK_ONLY_BUILDERS:
            if on_asynctask:
                caveat = SIGN_IN_CAVEAT
            else:
                reason = IN_PROCESS_UNAVAILABLE.get(name)
        elif name not in INPUT_BUILDERS:
            reason = f"{name} has no input resolver in the API yet (G3-798)."
        availability[name] = {"available": reason is None, "reason": reason, "caveat": caveat}
    return availability


def _run_on_asynctask(
    client: AsyncTaskClient, envelope: dict, tool_name: str, geneset_ids: list[int]
) -> dict[str, Any]:
    """Submit, wait a bounded time, and return the output or raise.

    :raises ToolRunPending: If the run is still going at the deadline.
    :raises ToolRunFailed: If it finished without completing.
    """
    state = client.submit(envelope, name=f"{tool_name}: " + ", ".join(map(str, geneset_ids)))
    state = client.wait(
        state,
        timeout=settings.ASYNCTASK_WAIT_SECONDS,
        poll_interval=settings.ASYNCTASK_POLL_SECONDS,
    )
    if not state.finished:
        raise ToolRunPending(tool_name, geneset_ids, state.run_id, state.status)
    if state.status != COMPLETED:
        raise ToolRunFailed(
            f"{tool_name} run {state.run_id} ended {state.status}. AsyncTask records no "
            f"cause; see Temporal workflow {state.workflow_id}."
        )
    return {"run_id": state.run_id, "result": state.result}


def run_tool(
    cursor: Cursor,
    tool_name: str,
    geneset_ids: list[int],
    user: User | None = None,
    parameters: dict[str, Any] | None = None,
    runner: ToolRunner | None = None,
) -> dict[str, Any]:
    """Gate, resolve, run and shape any registered tool.

    :param cursor: The database cursor.
    :param tool_name: A name from :func:`available_tools`.
    :param geneset_ids: The gene sets to analyse.
    :param user: The requesting user, or None for anonymous.
    :param parameters: Per-tool options; each builder documents what it reads.
    :param runner: In-process execution backend, used when the run does not go to
        AsyncTask.
    :return: ``{tool, geneset_ids, gene_counts, caveat, result, executed_by, run_id}``.
    :raises UnknownToolError: If the tool is not registered.
    :raises ValueError: If the tool cannot run in this environment.
    :raises SignInRequired: If the tool needs AsyncTask and the caller is anonymous.
    :raises ToolRequestError: If the request does not suit the tool.
    :raises UnauthorizedException: If any gene set is not readable by the caller.
    :raises ToolRunPending: If an AsyncTask run outlasts the wait.
    :raises ToolRunFailed: If an AsyncTask run fails.
    """
    parameters = parameters or {}
    state = tool_availability().get(tool_name)
    if state is None:
        raise UnknownToolError(f"No tool registered as {tool_name!r}.")
    if not state["available"]:
        raise ValueError(state["reason"])

    asynctask = asynctask_client_for(user)
    if tool_name in ASYNCTASK_ONLY_BUILDERS and asynctask is None:
        raise SignInRequired(f"{tool_name} runs on AsyncTask, which requires signing in.")

    # Before anything else: the tools know nothing about users, so a missing gate here
    # would let a caller read gene sets through a tool result.
    _gate_geneset_access(cursor, user, geneset_ids)

    memberships = db_tool_input.gene_symbols_by_geneset(cursor, geneset_ids)
    shaped = {
        "tool": tool_name,
        "geneset_ids": geneset_ids,
        "gene_counts": {key: len(genes) for key, genes in memberships.items()},
        "caveat": TOOL_CAVEATS.get(tool_name),
    }

    if tool_name in ASYNCTASK_ONLY_BUILDERS:
        envelope = ASYNCTASK_ONLY_BUILDERS[tool_name](cursor, geneset_ids, memberships, parameters)
    else:
        tool = load_tool(tool_name)
        # Validated here even for AsyncTask, so a bad request fails now with the tool's
        # own message rather than minutes later as an opaque failed run. Dumped in JSON
        # mode so database types (Decimal, tuples) cross the wire as the schema expects.
        tool_input = tool.tool_input(
            **INPUT_BUILDERS[tool_name](cursor, geneset_ids, memberships, parameters)
        )
        if asynctask is None:
            output = (runner or InProcessToolRunner()).run(tool, tool_input)
            return {
                **shaped,
                "executed_by": "in_process",
                "run_id": None,
                "result": output.model_dump(mode="json"),
            }
        envelope = {"tool": tool_name, "input": tool_input.model_dump(mode="json")}

    return {
        **shaped,
        "executed_by": "asynctask",
        **_run_on_asynctask(asynctask, envelope, tool_name, geneset_ids),
    }


def get_tool_run(run_id: int, user: User | None) -> dict[str, Any]:
    """A tool run's status, and its output once complete.

    Ownership is AsyncTask's check, made as this user: another user's run comes back 403
    from AsyncTask and is passed through as such.

    :raises SignInRequired: If the caller is anonymous.
    :raises ValueError: If this environment does not use AsyncTask.
    """
    if not asynctask_configured():
        raise ValueError("Tool runs are not sent to AsyncTask in this environment.")
    client = asynctask_client_for(user)
    if client is None:
        raise SignInRequired("Reading a tool run requires signing in.")
    state = client.get(run_id)
    return {
        "run_id": state.run_id,
        "status": state.status,
        "workflow_id": state.workflow_id,
        "result": state.result,
    }
