"""Service functions for running the ported analysis tools.

The flow is the same for every tool and worth keeping that way as more are added:

1. **gate** -- confirm the caller may read every gene set they named;
2. **resolve** -- turn gene set ids into the tool's input (`geneweaver.db.tool_input`);
3. **run** -- on AsyncTask when it is configured and the caller is signed in, otherwise
   in-process through a `ToolRunner`;
4. **shape** -- map the tool's output onto the API schema.

**Running an analysis requires a signed-in user**, in every environment. Where AsyncTask is
configured (`ASYNCTASK_API_URL`) the run goes there as that user -- including MSET and
PhenomeMap, whose native binaries only its worker images carry. Where it is not, the seven
pure-Python tools run in-process, still only for a signed-in user.
"""

import importlib.metadata
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from geneweaver.db import geneset as db_geneset
from geneweaver.db import tool_input as db_tool_input
from geneweaver.tools.framework.payload_size import check_payload_size
from geneweaver.tools.mset.schema import MSETInput
from geneweaver.tools.phenome_map.schema import PhenomeMapInput
from geneweaver.tools.upset import UpSet, UpSetInput
from psycopg import Cursor
from pydantic import ValidationError

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

    Runs are refused for anonymous callers before this is reached (`_require_user`), but
    the gate still treats a missing user as id 0, the public audience, so it fails closed
    if it is ever called without one.

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


@dataclass
class PreparedUpSet:
    """An UpSet run with every database read done, ready to execute without a connection."""

    geneset_ids: list[int]
    gene_counts: dict[str, int]
    tool_input: UpSetInput
    asynctask: AsyncTaskClient | None


def prepare_upset(
    cursor: Cursor,
    geneset_ids: list[int],
    user: User | None = None,
    include_zeros: bool = False,
    include_homology: bool = False,
) -> PreparedUpSet:
    """Gate and resolve an UpSet run: everything that needs the database.

    :raises SignInRequired: If the caller is anonymous.
    :raises UnauthorizedException: If any gene set is not readable by the caller.
    """
    _require_user(user)
    _gate_geneset_access(cursor, user, geneset_ids)
    memberships = resolve_memberships(cursor, geneset_ids, include_homology)
    return PreparedUpSet(
        geneset_ids=geneset_ids,
        gene_counts={key: len(genes) for key, genes in memberships.items()},
        tool_input=UpSetInput(
            geneset_ids=[str(geneset_id) for geneset_id in geneset_ids],
            gene_memberships=memberships,
            include_zeros=include_zeros,
            include_homology=include_homology,
        ),
        # The Analyze page's default tool comes through here rather than `run_tool`, so it
        # must route the same way or the most-used run would never reach AsyncTask.
        asynctask=asynctask_client_for(user),
    )


def execute_upset(prepared: PreparedUpSet, runner: ToolRunner | None = None) -> UpSetResult:
    """Run a prepared UpSet, in-process or on AsyncTask. Touches no database.

    :raises ToolRequestError: If the payload is too large to submit.
    :raises ToolRunPending: If an AsyncTask run outlasts the wait.
    :raises ToolRunFailed: If an AsyncTask run fails.
    """
    if prepared.asynctask is None:
        output = (runner or InProcessToolRunner()).run(UpSet(), prepared.tool_input)
        intersections = [(item.genesets, item.size) for item in output.intersections]
    else:
        envelope = {"tool": "upset", "input": prepared.tool_input.model_dump(mode="json")}
        _check_size(envelope)
        shaped = {
            "tool": "upset",
            "geneset_ids": prepared.geneset_ids,
            "gene_counts": prepared.gene_counts,
            "caveat": None,
        }
        ran = _run_on_asynctask(prepared.asynctask, envelope, shaped)
        intersections = [
            (item["genesets"], item["size"]) for item in ran["result"]["intersections"]
        ]

    return UpSetResult(
        geneset_ids=prepared.geneset_ids,
        gene_counts=prepared.gene_counts,
        intersections=[
            UpSetIntersection(geneset_ids=genesets, size=size) for genesets, size in intersections
        ],
    )


def run_upset(
    cursor: Cursor,
    geneset_ids: list[int],
    user: User | None = None,
    include_zeros: bool = False,
    runner: ToolRunner | None = None,
    include_homology: bool = False,
) -> UpSetResult:
    """Run UpSet over the given gene sets and return the exclusive intersection sizes.

    `prepare_upset` then `execute_upset`. The endpoint calls the two halves itself, so it
    can release its database connection before a remote wait; this is for everyone else.

    :param cursor: The database cursor.
    :param geneset_ids: The gene sets to intersect.
    :param user: The requesting user, or None for anonymous.
    :param include_zeros: Emit combinations with no genes.
    :param runner: Execution backend; defaults to running in-process.
    :param include_homology: Merge homologous genes across the gene sets.
    :return: The intersection sizes, largest first.
    :raises UnauthorizedException: If any gene set is not readable by the caller.
    """
    return execute_upset(
        prepare_upset(
            cursor,
            geneset_ids,
            user=user,
            include_zeros=include_zeros,
            include_homology=include_homology,
        ),
        runner,
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
    """The request cannot be run as asked: the caller must change it (422).

    Raised for every input problem -- a parameter the tool's schema rejects, the wrong
    number of gene sets, an oversized payload -- and always *before* anything is submitted,
    so a bad request never becomes an opaque failed run.
    """


class ToolUnavailable(Exception):
    """The tool cannot run in this environment, whatever the request (409).

    Its own type rather than any ValueError, so a malformed parameter -- pydantic's
    ValidationError is a ValueError -- can never be reported as a deployment conflict.
    """


class SignInRequired(Exception):
    """The caller is anonymous, and running an analysis requires signing in."""


def precheck_run(tool_name: str | None, user: User | None) -> None:
    """The checks a run endpoint makes *before* it opens a database connection.

    Unknown tool first (404: there is no analysis to sign in for), then sign-in (401). Both
    are pure, so an anonymous request is refused without leasing a connection -- otherwise it
    could wait on, or fail at, an exhausted pool instead of getting its 401. `prepare_*`
    repeats them, so a caller that skips this is still refused.

    :param tool_name: The tool, or None for the UpSet endpoint, whose tool is fixed.
    :raises UnknownToolError: If `tool_name` is not registered.
    :raises SignInRequired: If the caller is anonymous.
    """
    if tool_name is not None and tool_name not in available_tools():
        raise UnknownToolError(f"No tool registered as {tool_name!r}.")
    _require_user(user)


def _require_user(user: User | None) -> None:
    """Refuse an anonymous run before any database work.

    :raises SignInRequired: If there is no signed-in user.
    """
    if user is None:
        raise SignInRequired("Sign in to run an analysis.")


class ToolRunPending(Exception):
    """The run was accepted but had not finished within the wait; poll it by id.

    The body carries everything the completed response would except the result -- gene
    counts and caveat included -- so a client that polls to completion can assemble the
    same shape it would have got synchronously.
    """

    def __init__(self, shaped: dict[str, Any], run_id: int, status: str) -> None:
        super().__init__(f"{shaped['tool']} run {run_id} is still {status}.")
        self.body = {**shaped, "run_id": run_id, "status": status}


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


_TRUE = {"true", "1", "yes", "on", "included", "enabled"}
_FALSE = {"false", "0", "no", "off", "excluded", "disabled"}


def flag(parameters: dict[str, Any], key: str, default: bool) -> bool:
    """Read a yes/no option strictly.

    Not ``bool(value)``: ``bool("false")`` is True, which would silently run the opposite
    analysis. Legacy's own spellings (``"Included"``, ``"Enabled"``) are accepted, since
    that is what its forms and API sent.

    :raises ToolRequestError: For anything that is not recognisably yes or no.
    """
    value = parameters.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in _TRUE | _FALSE:
        return value.strip().lower() in _TRUE
    raise ToolRequestError(f"{key} must be true or false, not {value!r}.")


#: Tools whose memberships merge homologous genes when ``include_homology`` is set --
#: legacy's per-tool "Homology" option. Combine reads the option itself (it merges by
#: ortholog pairs into its own matrix); BooleanAlgebra always annotates homology; MSET
#: compares one species against its own gene space and had no such option.
HOMOLOGY_TOOLS = frozenset(
    {
        "upset",
        "dbscan",
        "hypergeometric",
        "jaccard_clustering",
        "jaccard_similarity",
        "phenome_map",
    }
)


def resolve_memberships(
    cursor: Cursor, geneset_ids: list[int], include_homology: bool = False
) -> dict[str, list[str]]:
    """Each gene set's genes, with homologous genes merged when asked."""
    if include_homology:
        return db_tool_input.homologous_gene_symbols_by_geneset(cursor, geneset_ids)
    return db_tool_input.gene_symbols_by_geneset(cursor, geneset_ids)


def _deletion_scopes(
    cursor: Cursor, geneset_ids: list[int], parameters: dict[str, Any]
) -> dict[tuple[int, int], tool_inputs.PairScope] | None:
    """Pairwise-deletion scopes when the option is on, querying only platforms in play."""
    if not flag(parameters, "pairwise_deletion", False):
        return None
    platforms = db_tool_input.geneset_platforms(cursor, geneset_ids)
    needed = tool_inputs.deletion_platforms(geneset_ids, platforms)
    genes = {
        platform: db_tool_input.platform_gene_symbols(cursor, platform) for platform in needed
    }
    return tool_inputs.pairwise_deletion_scopes(geneset_ids, platforms, genes)


# --- per-tool input builders -------------------------------------------------------
#
# Each takes the cursor, the requested gene set ids, their already-resolved memberships,
# and the caller's parameters, and returns the keyword arguments for that tool's input
# model. Signatures are uniform so `run_tool` needs no per-tool branching.


def _upset_input(cursor, geneset_ids, memberships, parameters) -> dict:
    return {
        "geneset_ids": _as_strings(geneset_ids),
        "gene_memberships": memberships,
        "include_zeros": flag(parameters, "include_zeros", False),
        "include_homology": flag(parameters, "include_homology", False),
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
    scopes = _deletion_scopes(cursor, geneset_ids, parameters)
    return {
        "geneset_ids": _as_strings(geneset_ids),
        "pairs": tool_inputs.contingency_pairs(memberships, geneset_ids, scopes),
    }


def _jaccard_clustering_input(cursor, geneset_ids, memberships, parameters) -> dict:
    return {
        "geneset_ids": _as_strings(geneset_ids),
        # Case-insensitive: legacy's form and API send "Average", "Ward", ...
        "method": str(parameters.get("method", "average")).lower(),
        "similarity": tool_inputs.similarity_matrix(memberships, geneset_ids),
    }


def _jaccard_similarity_input(cursor, geneset_ids, memberships, parameters) -> dict:
    scopes = _deletion_scopes(cursor, geneset_ids, parameters)
    return {
        "geneset_ids": _as_strings(geneset_ids),
        "include_homology": flag(parameters, "include_homology", False),
        "p_value_threshold": float(parameters.get("p_value_threshold", 0.05)),
        "pairs": tool_inputs.jaccard_pair_counts(memberships, geneset_ids, scopes),
        "distributions": db_tool_input.jaccard_distributions(cursor),
    }


def _combine_input(cursor, geneset_ids, memberships, parameters) -> dict:
    include_homology = flag(parameters, "include_homology", True)
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


#: BooleanAlgebra relations. The tool treats anything but union and except as an
#: intersection, so an unchecked typo would silently run the wrong operation.
BOOLEAN_RELATIONS = frozenset({"union", "intersection", "intersect", "except"})


def _boolean_algebra_input(cursor, geneset_ids, memberships, parameters) -> dict:
    relation = str(parameters.get("relation", "union")).lower()
    if relation not in BOOLEAN_RELATIONS:
        raise ToolRequestError(
            f"relation must be one of {sorted(BOOLEAN_RELATIONS)}, not {relation!r}."
        )
    at_least = int(parameters.get("at_least", 2))
    if at_least < 1:
        raise ToolRequestError(f"at_least must be 1 or more, not {at_least}.")
    species = db_tool_input.species_by_geneset(cursor, geneset_ids)
    # Distinct species, not one per gene set: the tool groups genes by species to decide
    # what can be identified across them, and a repeated species id would double-count.
    species_ids = sorted({species.get(geneset_id, 0) for geneset_id in geneset_ids})
    return {
        "relation": relation,
        "at_least": at_least,
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


#: MSET options a caller may set; anything else is the tool's own default.
MSET_PARAMETERS = ("number_of_samples", "over_representation")


def _mset_envelope(cursor, geneset_ids, memberships, parameters) -> dict:
    """Compare two gene sets against their species' full gene space.

    The background is sent as a reference the worker resolves from the database (G3-784),
    never inline: the universe is ~100,000 identifiers, at or over Temporal's 2 MiB limit.

    Validated against `MSETInput` itself, with the backgrounds stubbed because the worker
    fills them: pydantic's parsing, not Python casts -- `bool("false")` is True, which
    would silently select the opposite test.
    """
    if len(geneset_ids) != 2:
        raise ToolRequestError(
            f"MSET compares exactly two gene sets; {len(geneset_ids)} were given."
        )
    # The worker's resolver refuses a mixed-species universe; refusing here makes that a
    # 422 now instead of a guaranteed failed run.
    species = db_tool_input.species_by_geneset(cursor, geneset_ids)
    if len(set(species.values())) > 1:
        raise ToolRequestError(
            "MSET cannot compare gene sets from different species "
            f"(found species {sorted(set(species.values()))} across gene sets {geneset_ids})."
        )
    first, second = (str(geneset_id) for geneset_id in geneset_ids)
    requested = {
        "group_1_genes": memberships.get(first, []),
        "group_2_genes": memberships.get(second, []),
        **{key: parameters[key] for key in MSET_PARAMETERS if key in parameters},
    }
    validated = MSETInput(**requested, group_1_background=[], group_2_background=[])
    return {
        "tool": "mset",
        "input": validated.model_dump(
            mode="json", include=set(requested) | {"number_of_samples", "over_representation"}
        ),
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
    # pydantic parses the options (strictly for the booleans: "false" is False).
    validated = PhenomeMapInput(
        gene_sets=memberships,
        **{key: parameters[key] for key in PHENOME_MAP_PARAMETERS if key in parameters},
    )
    return {"tool": "phenome_map", "input": validated.model_dump(mode="json")}


#: Tool name -> envelope builder, for tools that run only on AsyncTask.
ASYNCTASK_ONLY_BUILDERS: dict[str, Callable[..., dict]] = {
    "mset": _mset_envelope,
    "phenome_map": _phenome_map_envelope,
}


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
            if not on_asynctask:
                reason = IN_PROCESS_UNAVAILABLE.get(name)
        elif name not in INPUT_BUILDERS:
            reason = f"{name} has no input resolver in the API yet (G3-798)."
        availability[name] = {"available": reason is None, "reason": reason, "caveat": caveat}
    return availability


def _check_size(envelope: dict) -> None:
    """Refuse an envelope over Temporal's payload limit before AsyncTask sees it.

    The gene-set cap does not bound this -- twenty large gene sets can still exceed 2 MiB
    -- and past the limit the failure is a transport error naming no tool or field.

    :raises ToolRequestError: With the size and the largest field.
    """
    try:
        check_payload_size(envelope)
    except ValueError as error:
        raise ToolRequestError(str(error)) from error


def _run_on_asynctask(
    client: AsyncTaskClient, envelope: dict, shaped: dict[str, Any]
) -> dict[str, Any]:
    """Submit, wait a bounded time, and return the output or raise.

    :raises ToolRunPending: If the run is still going at the deadline.
    :raises ToolRunFailed: If it finished without completing.
    """
    tool_name = shaped["tool"]
    label = f"{tool_name}: " + ", ".join(map(str, shaped["geneset_ids"]))
    state = client.submit(envelope, name=label)
    state = client.wait(
        state,
        timeout=settings.ASYNCTASK_WAIT_SECONDS,
        poll_interval=settings.ASYNCTASK_POLL_SECONDS,
    )
    if not state.finished:
        raise ToolRunPending(shaped, state.run_id, state.status)
    if state.status != COMPLETED:
        raise ToolRunFailed(
            f"{tool_name} run {state.run_id} ended {state.status}. AsyncTask records no "
            f"cause; see Temporal workflow {state.workflow_id}."
        )
    return {"run_id": state.run_id, "result": state.result}


@dataclass
class PreparedRun:
    """A tool run with every database read done, ready to execute without a connection.

    Exactly one of ``envelope`` (AsyncTask) and ``tool``/``tool_input`` (in-process) is
    used, chosen by whether ``asynctask`` is set.
    """

    shaped: dict[str, Any]
    asynctask: AsyncTaskClient | None
    envelope: dict[str, Any] | None = None
    tool: Any = None
    tool_input: Any = None


def _validated(tool_name: str, build: Callable[[], Any]) -> Any:
    """Build a tool's input, turning any rejection of the request into a 422.

    Covers pydantic's ValidationError and the builders' own conversions (`int("x")`), both
    ValueErrors, plus the TypeError a null parameter raises -- all of them the caller's to
    fix, none of them a server conflict.
    """
    try:
        return build()
    except ToolRequestError:
        raise
    except ValidationError as error:
        raise ToolRequestError(f"Invalid input for {tool_name}: {error}") from error
    except (ValueError, TypeError) as error:
        raise ToolRequestError(f"Invalid parameter for {tool_name}: {error}") from error


def prepare_tool_run(
    cursor: Cursor,
    tool_name: str,
    geneset_ids: list[int],
    user: User | None = None,
    parameters: dict[str, Any] | None = None,
) -> PreparedRun:
    """Gate, resolve and validate a run: everything that needs the database.

    Validation happens here for every tool and both backends, so a bad request fails now
    with the tool's own message rather than minutes later as an opaque failed run.

    :raises UnknownToolError: If the tool is not registered.
    :raises ToolUnavailable: If the tool cannot run in this environment.
    :raises SignInRequired: If the caller is anonymous.
    :raises UnauthorizedException: If any gene set is not readable by the caller.
    :raises ToolRequestError: If the request does not suit the tool.
    """
    parameters = parameters or {}
    state = tool_availability().get(tool_name)
    if state is None:
        raise UnknownToolError(f"No tool registered as {tool_name!r}.")
    # Before availability: every registered analysis refuses an anonymous caller the same
    # way (401), whatever this environment can run. Otherwise an anonymous MSET request where
    # AsyncTask is not configured got 409, and the answer depended on deployment and tool.
    _require_user(user)
    if not state["available"]:
        raise ToolUnavailable(state["reason"])

    asynctask = asynctask_client_for(user)
    if tool_name in ASYNCTASK_ONLY_BUILDERS and asynctask is None:
        # Signed in, AsyncTask configured, yet no client: the user has no token to act as.
        raise SignInRequired(f"{tool_name} runs on AsyncTask, which needs a signed-in session.")

    # Before anything else: the tools know nothing about users, so a missing gate here
    # would let a caller read gene sets through a tool result.
    _gate_geneset_access(cursor, user, geneset_ids)

    include_homology = tool_name in HOMOLOGY_TOOLS and _validated(
        tool_name, lambda: flag(parameters, "include_homology", False)
    )
    memberships = resolve_memberships(cursor, geneset_ids, include_homology)
    shaped = {
        "tool": tool_name,
        "geneset_ids": geneset_ids,
        "gene_counts": {key: len(genes) for key, genes in memberships.items()},
        "caveat": TOOL_CAVEATS.get(tool_name),
    }

    if tool_name in ASYNCTASK_ONLY_BUILDERS:
        envelope = _validated(
            tool_name,
            lambda: ASYNCTASK_ONLY_BUILDERS[tool_name](
                cursor, geneset_ids, memberships, parameters
            ),
        )
        _check_size(envelope)
        return PreparedRun(shaped=shaped, asynctask=asynctask, envelope=envelope)

    tool = load_tool(tool_name)
    tool_input = _validated(
        tool_name,
        lambda: tool.tool_input(
            **INPUT_BUILDERS[tool_name](cursor, geneset_ids, memberships, parameters)
        ),
    )
    if asynctask is None:
        return PreparedRun(shaped=shaped, asynctask=None, tool=tool, tool_input=tool_input)
    # JSON mode so database types (Decimal, tuples) cross the wire as the schema expects.
    envelope = {"tool": tool_name, "input": tool_input.model_dump(mode="json")}
    _check_size(envelope)
    return PreparedRun(shaped=shaped, asynctask=asynctask, envelope=envelope)


def execute_tool_run(prepared: PreparedRun, runner: ToolRunner | None = None) -> dict[str, Any]:
    """Run a prepared tool, in-process or on AsyncTask. Touches no database.

    :return: ``{tool, geneset_ids, gene_counts, caveat, result, executed_by, run_id}``.
    :raises ToolRunPending: If an AsyncTask run outlasts the wait.
    :raises ToolRunFailed: If an AsyncTask run fails.
    """
    if prepared.asynctask is None:
        output = (runner or InProcessToolRunner()).run(prepared.tool, prepared.tool_input)
        return {
            **prepared.shaped,
            "executed_by": "in_process",
            "run_id": None,
            "result": output.model_dump(mode="json"),
        }
    return {
        **prepared.shaped,
        "executed_by": "asynctask",
        **_run_on_asynctask(prepared.asynctask, prepared.envelope, prepared.shaped),
    }


def run_tool(
    cursor: Cursor,
    tool_name: str,
    geneset_ids: list[int],
    user: User | None = None,
    parameters: dict[str, Any] | None = None,
    runner: ToolRunner | None = None,
) -> dict[str, Any]:
    """Gate, resolve, run and shape any registered tool.

    `prepare_tool_run` then `execute_tool_run`. The endpoint calls the two halves itself,
    so it can release its database connection before a remote wait; this is for everyone
    else. Raises whatever either half raises.

    :param cursor: The database cursor.
    :param tool_name: A name from :func:`available_tools`.
    :param geneset_ids: The gene sets to analyse.
    :param user: The requesting user, or None for anonymous.
    :param parameters: Per-tool options; each builder documents what it reads.
    :param runner: In-process execution backend, used when the run does not go to
        AsyncTask.
    """
    prepared = prepare_tool_run(cursor, tool_name, geneset_ids, user=user, parameters=parameters)
    return execute_tool_run(prepared, runner)


def get_tool_run(run_id: int, user: User | None) -> dict[str, Any]:
    """A tool run's status, and its output once complete.

    Ownership is AsyncTask's check, made as this user: another user's run comes back 403
    from AsyncTask and is passed through as such.

    :raises SignInRequired: If the caller is anonymous.
    :raises ToolUnavailable: If this environment does not use AsyncTask.
    """
    if not asynctask_configured():
        raise ToolUnavailable("Tool runs are not sent to AsyncTask in this environment.")
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
