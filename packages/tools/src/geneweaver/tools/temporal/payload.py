"""Bounding the size of a tool payload crossing the Temporal boundary.

Temporal's default gRPC message limit is 2 MiB, and every argument and result is also
written into workflow history, so a large payload costs storage and replay time on top of
the transfer. A payload over the limit is refused by the server with a transport-level
error that names no tool and no field.

This check exists so that failure is instead attributable: it names the tool, the measured
size and the limit. It is a guard, not a solution -- see :data:`INLINE_PAYLOAD_NOTE`.

Measured payload sizes for MSET, whose two background universes dominate its request
(synthetic identifiers of realistic shape, 300 genes per group, JSON-encoded):

    universe    gene symbols    MGI accessions
      20,000        0.41 MiB          0.58 MiB
      50,000        1.01 MiB          1.44 MiB
     100,000        2.01 MiB          2.87 MiB   <-- over the 2 MiB default
     150,000        3.01 MiB          4.30 MiB

``mset/tool.py`` puts a full universe at ~100,000 identifiers, so realistic MSET requests
sit at or just over the limit. This has **not** been re-measured against a real universe
from the database; that measurement is still outstanding and is why MSET is not yet
declared ready for AsyncTask execution (see ``MSET_ASYNCTASK_BLOCKED``).
"""

import json
from typing import Any

#: Temporal's default `GRPC_MAX_MESSAGE_SIZE`. Payloads above this are refused by the
#: server, so the useful limit is below it -- history entries carry overhead beyond the
#: payload itself.
TEMPORAL_DEFAULT_LIMIT_BYTES = 2 * 1024 * 1024

#: Headroom for Temporal's own framing and metadata, so a payload that passes this check
#: is not then refused by the server for being marginally over.
MAX_PAYLOAD_BYTES = int(TEMPORAL_DEFAULT_LIMIT_BYTES * 0.9)

#: Why the guard is not the fix. Recorded here rather than in a ticket comment because the
#: next person to hit the limit needs it.
INLINE_PAYLOAD_NOTE = (
    "Passing a resolved gene universe inline sends megabytes of reference data through "
    "Temporal on every run, and into workflow history. The fix is to pass a compact "
    "universe reference (species + identifier type + version) and resolve it inside the "
    "activity. That requires the activity to reach the database, which it deliberately "
    "does not today -- the tools are pure by design -- so it is a scope decision for "
    "G3-784/G3-798, not a change to make here."
)

#: Tools not yet cleared to run through AsyncTask, and why. The API's in-process runner is
#: unaffected: these limits are Temporal's, not the tool's.
MSET_ASYNCTASK_BLOCKED = (
    "MSET sends two full gene universes inline, which measures at or above Temporal's "
    "2 MiB default message limit for a ~100,000-identifier universe. " + INLINE_PAYLOAD_NOTE
)

ASYNCTASK_BLOCKED_TOOLS: dict[str, str] = {"mset": MSET_ASYNCTASK_BLOCKED}


def payload_size(input_data: Any) -> int:
    """Serialized size of a tool payload in bytes, as Temporal would encode it."""
    return len(json.dumps(input_data, default=str).encode())


def check_payload_size(input_data: dict, limit: int | None = None) -> int:
    """Refuse a payload too large for Temporal, with an attributable message.

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
        key: len(value)
        for key, value in tool_input.items()
        if isinstance(value, (list, str))
    }
    if not sizes:
        return ""
    field = max(sizes, key=lambda key: sizes[key])
    return f"; the largest field is {field!r} with {sizes[field]} entries"
