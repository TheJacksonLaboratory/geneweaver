"""Service functions for running the ported analysis tools.

The flow is the same for every tool and worth keeping that way as more are added:

1. **gate** -- confirm the caller may read every gene set they named;
2. **resolve** -- turn gene set ids into the tool's input (`geneweaver.db.tool_input`);
3. **run** -- hand the input to a `ToolRunner`, which today executes in-process and
   later dispatches to AsyncTask;
4. **shape** -- map the tool's output onto the API schema.

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

from geneweaver.api.core.exceptions import UnauthorizedException
from geneweaver.api.schemas.auth import User
from geneweaver.api.schemas.tools import UpSetIntersection, UpSetResult
from geneweaver.api.services import tool_inputs
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

    runner = runner or InProcessToolRunner()
    output = runner.run(
        UpSet(),
        UpSetInput(
            geneset_ids=[str(geneset_id) for geneset_id in geneset_ids],
            gene_memberships=memberships,
            include_zeros=include_zeros,
        ),
    )

    return UpSetResult(
        geneset_ids=geneset_ids,
        gene_counts={key: len(genes) for key, genes in memberships.items()},
        intersections=[
            UpSetIntersection(geneset_ids=item.genesets, size=item.size)
            for item in output.intersections
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


def tool_availability() -> dict[str, dict[str, Any]]:
    """What each registered tool's state is, for the UI's picker.

    Returned from the API rather than hardcoded in the front end so the two cannot drift:
    the page previously listed five of the nine tools, which made the port look narrower
    than it is.
    """
    availability = {}
    for name in available_tools():
        reason = IN_PROCESS_UNAVAILABLE.get(name)
        if reason is None and name not in INPUT_BUILDERS:
            reason = f"{name} has no input resolver in the API yet (G3-798)."
        availability[name] = {
            "available": reason is None,
            "reason": reason,
            "caveat": TOOL_CAVEATS.get(name),
        }
    return availability


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
    :param runner: Execution backend; defaults to running in-process.
    :return: ``{tool, geneset_ids, gene_counts, caveat, result}``.
    :raises UnknownToolError: If the tool is not registered.
    :raises ValueError: If the tool cannot run in this process.
    :raises UnauthorizedException: If any gene set is not readable by the caller.
    """
    parameters = parameters or {}

    if tool_name not in INPUT_BUILDERS or tool_name in IN_PROCESS_UNAVAILABLE:
        state = tool_availability().get(tool_name)
        if state is None:
            raise UnknownToolError(f"No tool registered as {tool_name!r}.")
        raise ValueError(state["reason"])

    # Before anything else: the tools know nothing about users, so a missing gate here
    # would let a caller read gene sets through a tool result.
    _gate_geneset_access(cursor, user, geneset_ids)

    tool = load_tool(tool_name)
    memberships = db_tool_input.gene_symbols_by_geneset(cursor, geneset_ids)
    tool_input = tool.tool_input(
        **INPUT_BUILDERS[tool_name](cursor, geneset_ids, memberships, parameters)
    )

    runner = runner or InProcessToolRunner()
    output = runner.run(tool, tool_input)

    return {
        "tool": tool_name,
        "geneset_ids": geneset_ids,
        "gene_counts": {key: len(genes) for key, genes in memberships.items()},
        "caveat": TOOL_CAVEATS.get(tool_name),
        "result": output.model_dump(mode="json"),
    }
