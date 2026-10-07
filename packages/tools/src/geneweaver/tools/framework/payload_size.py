"""Bounding the size of a tool payload crossing the Temporal boundary.

Pure -- no `temporalio` import, here or in this package's `__init__` -- so the GeneWeaver API,
which installs `geneweaver-tools` without the `temporal` extra, can refuse an oversized run
*before* handing it to AsyncTask. `geneweaver.tools.temporal.payload` re-exports all of it
for the workflow and activity; the measurements and rationale are documented there.
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
