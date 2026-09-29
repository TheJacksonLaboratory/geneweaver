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
    "MSET sends two full gene universes inline. A ~100,000-identifier universe measures "
    "1.82 MiB in gene symbols -- 89% of Temporal's 2 MiB limit -- and 2.68 MiB in MGI "
    "accessions, which is over it. " + INLINE_PAYLOAD_NOTE
)

ASYNCTASK_BLOCKED_TOOLS: dict[str, str] = {"mset": MSET_ASYNCTASK_BLOCKED}


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

    The primary guard, for the submission path: policy first, then size, so a blocked tool
    reports why it is blocked rather than a size that happens to be under the limit.

    :return: The measured payload size.
    """
    check_tool_allowed(input_data.get("tool", "unknown"))
    return check_payload_size(input_data)


def _largest_field(tool_input: dict) -> str:
    """Name the field responsible, so the error points at something actionable."""
    sizes = {
        key: len(value) for key, value in tool_input.items() if isinstance(value, (list, str))
    }
    if not sizes:
        return ""
    field = max(sizes, key=lambda key: sizes[key])
    return f"; the largest field is {field!r} with {sizes[field]} entries"
