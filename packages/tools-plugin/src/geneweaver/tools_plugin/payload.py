"""The shape and size of a tool request, checked before it crosses into Temporal.

Standard library only, so it is safe in workflow code and the GeneWeaver API can use it
without loading the Temporal SDK.

A request is ``{"tool": "upset", "input": {...}}``, optionally with a ``"universe"``
reference that the worker expands (G3-784). The tool's own input schema is checked by the
worker; here only what the workflow needs: that a tool is named, that it is allowed, and
that the request fits.

**Size.** Temporal's default gRPC message limit is 2 MiB, and every argument and result is
also written into workflow history. A payload over the limit is refused with a transport
error that names no tool and no field, which is why the size is checked here instead.

**Measuring it correctly matters.** ``json.dumps`` defaults to ``", "`` and ``": "``
separators; Temporal's converter emits compact JSON. Measuring with the defaults overstates
the payload by ~10.5%, enough to invert the verdict near the limit. :func:`payload_size`
encodes exactly as the converter does, and ``test_payload_size_matches_temporals_own_converter``
pins the two together byte for byte.

Measured MSET payloads with both gene universes inline (synthetic identifiers of realistic
shape, 300 genes per group, as Temporal encodes them):

    universe    gene symbols       MGI accessions
      20,000      0.368 MiB          0.542 MiB
      50,000      0.910 MiB          1.343 MiB
     100,000      1.817 MiB          2.678 MiB  <-- over, for the longer identifier
     150,000      2.720 MiB  <-- over    4.014 MiB  <-- over

So MSET now sends a universe reference instead, and its payload is a few kilobytes.
"""

import json
from typing import Any

#: Temporal's default `GRPC_MAX_MESSAGE_SIZE`. Payloads above this are refused by the
#: server.
TEMPORAL_DEFAULT_LIMIT_BYTES = 2 * 1024 * 1024

#: Bytes a `Payload` adds around its data (protobuf field framing plus the converter's
#: `encoding` metadata). Measured; asserted against the real converter in the tests.
PAYLOAD_FRAMING_BYTES = 28

#: Headroom for Temporal's own request framing beyond the payload, so a payload that passes
#: this check is not then refused by the server for being marginally over.
MAX_PAYLOAD_BYTES = int(TEMPORAL_DEFAULT_LIMIT_BYTES * 0.9)

#: Why a large payload is refused rather than sent, for the next person to hit the limit.
INLINE_PAYLOAD_NOTE = (
    "Passing reference data inline sends it through Temporal on every run, and into "
    "workflow history. Pass a compact reference instead and resolve it in the worker, as "
    "MSET's gene universe is (G3-784)."
)

#: Tools not cleared to run through AsyncTask, and why. Empty since G3-784: MSET was the
#: only entry, because it sent two full gene universes inline. Kept rather than deleted:
#: the size limit is a property of Temporal, and the next tool with a large inline input
#: needs somewhere to say so. The size guard still applies to every tool.
ASYNCTASK_BLOCKED_TOOLS: dict[str, str] = {}


def payload_size(input_data: Any) -> int:
    """Size in bytes of a tool payload as Temporal will encode it.

    Compact separators and the `Payload` framing, matching
    ``DataConverter.default.payload_converter``. Deliberately plain ``json`` rather than an
    import of the converter, so this is safe to call from workflow code inside Temporal's
    sandbox; the tests prove the two agree.
    """
    encoded = len(json.dumps(input_data, separators=(",", ":"), default=str).encode())
    return encoded + PAYLOAD_FRAMING_BYTES


def check_payload_size(input_data: dict, limit: int | None = None) -> int:
    """Refuse a payload too large for Temporal, with an attributable message.

    Call this *before* handing the payload to Temporal -- from the submission path, and
    again in the workflow before scheduling the activity. By the time the activity runs,
    the payload has already crossed two boundaries that could have refused it.

    :param input_data: The ``{"tool": ..., "input": {...}}`` payload.
    :param limit: Byte limit; defaults to :data:`MAX_PAYLOAD_BYTES`.
    :return: The measured size, so callers can log it.
    :raises ValueError: If the payload exceeds the limit.
    """
    bound = MAX_PAYLOAD_BYTES if limit is None else limit
    size = payload_size(input_data)
    if size > bound:
        tool = input_data.get("tool", "unknown")
        largest = _largest_field(input_data.get("input", {}))
        raise ValueError(
            f"The {tool} payload is {size / 1024 / 1024:.2f} MiB, over the "
            f"{bound / 1024 / 1024:.2f} MiB limit for a Temporal argument"
            f"{largest}. {INLINE_PAYLOAD_NOTE}"
        )
    return size


def _largest_field(tool_input: dict) -> str:
    """Name the field responsible, so the error points at something actionable."""
    sizes = {
        key: len(value) for key, value in tool_input.items() if isinstance(value, (list, str))
    }
    if not sizes:
        return ""
    field = max(sizes, key=lambda key: sizes[key])
    return f"; the largest field is {field!r} with {sizes[field]} entries"


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
    """Every check the workflow makes, for a caller to run before submitting.

    Policy first, then size, so a blocked tool reports why it is blocked rather than a size
    that happens to be under the limit. AsyncTask's own submission path passes the request
    straight to `start_workflow`, so the workflow repeats these checks.

    :return: The measured payload size.
    """
    check_tool_allowed(requested_tool(input_data))
    return check_payload_size(input_data)
