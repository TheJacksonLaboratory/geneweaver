"""Tests for the Temporal payload size guard.

The point of the guard is attribution: a payload over Temporal's limit is otherwise refused
by the server with a transport error naming neither the tool nor the field.
"""

import json
import random
import string

import pytest
from geneweaver.tools.temporal.activities import run_tool
from geneweaver.tools.temporal.payload import (
    ASYNCTASK_BLOCKED_TOOLS,
    MAX_PAYLOAD_BYTES,
    TEMPORAL_DEFAULT_LIMIT_BYTES,
    check_payload_size,
    payload_size,
)


def _symbols(count: int) -> list[str]:
    """Identifiers of realistic length, so measured sizes mean something."""
    random.seed(0)
    return [
        "".join(random.choices(string.ascii_uppercase, k=2))
        + "".join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(1, 8)))
        for _ in range(count)
    ]


def _mset_payload(universe: int) -> dict:
    return {
        "tool": "upset",  # not `mset`: that is blocked outright, tested separately
        "input": {
            "group_1_genes": _symbols(300),
            "group_2_genes": _symbols(300),
            "group_1_background": _symbols(universe),
            "group_2_background": _symbols(universe),
        },
    }


def test_the_guard_sits_below_temporals_own_limit() -> None:
    """A payload that passes must not then be refused by the server for framing overhead."""
    assert MAX_PAYLOAD_BYTES < TEMPORAL_DEFAULT_LIMIT_BYTES


def test_a_small_payload_passes_and_reports_its_size() -> None:
    """The ordinary case: allowed, and the measured size returned for logging."""
    payload = {"tool": "upset", "input": {"geneset_ids": [1, 2, 3]}}
    assert check_payload_size(payload) == payload_size(payload)


def test_a_payload_at_the_limit_is_allowed() -> None:
    """The boundary itself passes -- the check is `>`, not `>=`."""
    payload = {"tool": "upset", "input": {"genes": _symbols(10)}}
    assert check_payload_size(payload, limit=payload_size(payload)) > 0


def test_a_payload_one_byte_over_the_limit_is_refused() -> None:
    """One byte past the boundary is refused -- the check is strict."""
    payload = {"tool": "upset", "input": {"genes": _symbols(10)}}
    with pytest.raises(ValueError, match="over the"):
        check_payload_size(payload, limit=payload_size(payload) - 1)


def test_the_error_names_the_tool_and_the_offending_field() -> None:
    """Without this the operator cannot tell which input to shrink."""
    payload = _mset_payload(150_000)
    with pytest.raises(ValueError) as excinfo:
        check_payload_size(payload)
    message = str(excinfo.value)
    assert "upset" in message
    assert "group_1_background" in message or "group_2_background" in message
    assert "MiB" in message


def test_two_full_universes_exceed_temporals_default_limit() -> None:
    """The measurement behind the guard.

    `mset/tool.py` puts a full gene universe at ~100,000 identifiers. Two of them inline,
    JSON-encoded, cross Temporal's 2 MiB default -- which is why MSET is not cleared for
    AsyncTask execution rather than merely guarded.
    """
    size = payload_size(_mset_payload(100_000))
    assert size > TEMPORAL_DEFAULT_LIMIT_BYTES, (
        f"two 100k universes measured {size / 1024 / 1024:.2f} MiB; if this is now under "
        "the limit, re-measure against a real universe before clearing MSET"
    )


def test_a_realistic_small_universe_still_fits() -> None:
    """The guard must not refuse universes that are genuinely fine -- 20k is well under."""
    assert payload_size(_mset_payload(20_000)) < MAX_PAYLOAD_BYTES


def test_mset_is_not_cleared_for_asynctask() -> None:
    """PR #32 review: MSET must not be declared AsyncTask-ready until re-measured."""
    assert "mset" in ASYNCTASK_BLOCKED_TOOLS
    assert "G3-784" in ASYNCTASK_BLOCKED_TOOLS["mset"]


def test_running_mset_through_the_activity_explains_why_it_is_blocked() -> None:
    """A blocked tool fails with a reason, not a schema error from deep inside the tool."""
    with pytest.raises(ValueError, match="cannot run through AsyncTask yet"):
        run_tool({"tool": "mset", "input": {}})


def test_an_oversized_payload_fails_before_the_tool_is_loaded() -> None:
    """Refuse on size rather than spending the resolution and validation first."""
    with pytest.raises(ValueError, match="over the"):
        run_tool(_mset_payload(150_000))


def test_payload_size_matches_json_encoding() -> None:
    """The guard must measure what actually goes over the wire."""
    payload = {"tool": "upset", "input": {"genes": ["A", "B"]}}
    assert payload_size(payload) == len(json.dumps(payload).encode())
