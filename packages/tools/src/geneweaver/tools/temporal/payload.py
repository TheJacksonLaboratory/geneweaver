"""Bounding the size of a tool payload crossing the Temporal boundary.

Temporal's default gRPC message limit is 2 MiB, and every argument and result is also
written into workflow history, so a large payload costs storage and replay time on top of
the transfer. A payload over the limit is refused with a transport-level error that names
no tool and no field, which is why the size is checked here instead.

**Measuring it correctly matters.** ``json.dumps`` defaults to ``", "`` and ``": "``
separators; Temporal's converter emits compact JSON. Measuring with the defaults overstates
the payload by ~10.5%, which is enough to invert the verdict at the sizes MSET operates at.
:func:`payload_size` therefore encodes exactly as the converter does, and
``test_payload_size_matches_temporals_own_converter`` pins the two together byte-for-byte.

Measured MSET payloads -- its two background universes dominate the request (synthetic
identifiers of realistic shape, 300 genes per group, as Temporal encodes them):

    universe    gene symbols       MGI accessions
      20,000      0.368 MiB          0.542 MiB
      50,000      0.910 MiB          1.343 MiB
     100,000      1.817 MiB          2.678 MiB  <-- over, for the longer identifier
     150,000      2.720 MiB  <-- over    4.014 MiB  <-- over

So a full ~100,000-identifier universe (``mset/tool.py``) fits *only* with short gene
symbols, and at 89% of the limit; the same universe in MGI accessions does not. MSET is
blocked from AsyncTask rather than merely guarded, because that headroom is too thin to
depend on and has **not** been re-measured against a real universe from the database.
"""

# The size guard lives in `framework.payload_size` so the API can use it without temporalio;
# re-exported so the workflow, the activity and existing callers are unchanged.
from geneweaver.tools.framework.payload_size import (  # noqa: F401
    INLINE_PAYLOAD_NOTE,
    MAX_PAYLOAD_BYTES,
    PAYLOAD_FRAMING_BYTES,
    TEMPORAL_DEFAULT_LIMIT_BYTES,
    _largest_field,
    check_payload_size,
    payload_size,
)

#: Tools not cleared to run through AsyncTask, and why. Empty since G3-784: MSET was the
#: only entry, because it sent two full gene universes inline -- 1.82 MiB in gene symbols
#: for a ~100,000-identifier universe, 2.68 MiB in MGI accessions. It now sends a reference
#: that `temporal.resolvers` expands inside the activity, so the payload is the two member
#: lists and nothing else.
#:
#: Kept rather than deleted: the size limit is a property of Temporal, and the next tool
#: with a large inline input needs somewhere to say so. The size guard
#: (`framework.payload_size`) still applies to every tool.
ASYNCTASK_BLOCKED_TOOLS: dict[str, str] = {}


def requested_tool(input_data: object) -> str:
    """Read the tool name out of a request, rejecting anything malformed.

    AsyncTask sees this plugin's input schema as plain ``dict``, so its API does not require
    the key and a submission can arrive without it. Indexing directly would raise
    ``KeyError``, which is not a ``ValueError`` and so escaped the workflow's non-retryable
    wrapper -- putting the run back into Temporal's indefinite workflow-task retry.

    :raises ValueError: If the request is not a mapping, or has no usable ``tool``.
    """
    if not isinstance(input_data, dict):
        raise ValueError(
            f"A tool request must be an object with a 'tool' key; got {type(input_data).__name__}."
        )
    tool = input_data.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        raise ValueError(
            f"A tool request must name a tool in its 'tool' key; got {tool!r}. "
            "Expected {'tool': 'upset', 'input': {...}}."
        )
    return tool


def check_tool_allowed(tool: str) -> None:
    """Refuse a tool not yet cleared for AsyncTask execution.

    :raises ValueError: If the tool is blocked, with the reason.
    """
    if tool in ASYNCTASK_BLOCKED_TOOLS:
        raise ValueError(
            f"{tool} cannot run through AsyncTask yet. {ASYNCTASK_BLOCKED_TOOLS[tool]}"
        )


def check_submission(input_data: dict) -> int:
    """Validate a payload before it is handed to Temporal at all.

    Policy first, then size, so a blocked tool reports why it is blocked rather than a size
    that happens to be under the limit.

    **This has no caller in this repository, and cannot have one.** The submission path is
    AsyncTask's: its `TemporalAdapter.submit()` passes the request straight to
    `client.start_workflow()`. Until AsyncTask calls this (or runs a plugin validation hook),
    the earliest guard we control is `GeneWeaverToolWorkflow.run`, which is already past the
    first Temporal boundary. Exported deliberately so that wiring is a one-line change in
    AsyncTask rather than a reimplementation; tracked as a cross-repo item in
    `docs/v3/V3_ROADMAP_AND_GAP.md`.

    :return: The measured payload size.
    """
    check_tool_allowed(requested_tool(input_data))
    return check_payload_size(input_data)
