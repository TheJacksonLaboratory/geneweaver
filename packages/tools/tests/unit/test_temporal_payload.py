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
    PAYLOAD_FRAMING_BYTES,
    TEMPORAL_DEFAULT_LIMIT_BYTES,
    check_payload_size,
    check_submission,
    payload_size,
)


def _identifiers(count: int, kind: str = "symbol") -> list[str]:
    """Identifiers of realistic length, so measured sizes mean something.

    Both shapes matter: the verdict at a 100,000-gene universe differs between short gene
    symbols and long MGI accessions.
    """
    random.seed(0)
    if kind == "mgi":
        return [f"MGI:{random.randint(1000000, 9999999)}" for _ in range(count)]
    return [
        "".join(random.choices(string.ascii_uppercase, k=2))
        + "".join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(1, 8)))
        for _ in range(count)
    ]


def _mset_payload(universe: int, kind: str = "symbol") -> dict:
    """An MSET-shaped request, under a tool name that is not blocked.

    Uses `upset` so the size checks are reachable: `mset` is refused by policy before any
    measurement, which is tested separately.
    """
    return {
        "tool": "upset",
        "input": {
            "group_1_genes": _identifiers(300, kind),
            "group_2_genes": _identifiers(300, kind),
            "group_1_background": _identifiers(universe, kind),
            "group_2_background": _identifiers(universe, kind),
            "number_of_samples": 1000,
            "over_representation": True,
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
    payload = {"tool": "upset", "input": {"genes": _identifiers(10)}}
    assert check_payload_size(payload, limit=payload_size(payload)) > 0


def test_a_payload_one_byte_over_the_limit_is_refused() -> None:
    """One byte past the boundary is refused -- the check is strict."""
    payload = {"tool": "upset", "input": {"genes": _identifiers(10)}}
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


def test_a_full_universe_of_gene_symbols_fits_but_only_just() -> None:
    """The corrected measurement, and why MSET is blocked rather than merely guarded.

    An earlier version of this test asserted the opposite. It measured with `json.dumps`'s
    default `", "`/`": "` separators, which overstates the payload by ~10.5% -- enough to
    invert the verdict. Temporal emits compact JSON: this fixture is ~1.82 MiB, *under* the
    2 MiB limit, at 89% of it.
    """
    size = payload_size(_mset_payload(100_000, "symbol"))
    assert size < TEMPORAL_DEFAULT_LIMIT_BYTES
    assert size / TEMPORAL_DEFAULT_LIMIT_BYTES > 0.85, (
        "headroom has grown; re-check whether MSET still needs to be blocked"
    )


def test_the_same_universe_in_mgi_accessions_does_not_fit() -> None:
    """Identifier length decides it -- which is why the headroom above is not dependable."""
    assert payload_size(_mset_payload(100_000, "mgi")) > TEMPORAL_DEFAULT_LIMIT_BYTES


def test_a_larger_universe_does_not_fit_in_either_shape() -> None:
    """Beyond a full universe, identifier length stops mattering -- both are over."""
    for kind in ("symbol", "mgi"):
        assert payload_size(_mset_payload(150_000, kind)) > TEMPORAL_DEFAULT_LIMIT_BYTES


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


def test_payload_size_matches_temporals_own_converter() -> None:
    """Pins the pure measurement to the real converter, byte for byte.

    `payload_size` deliberately uses plain `json` so it is safe inside Temporal's workflow
    sandbox, which makes this the test that keeps it honest. If AsyncTask changes its data
    converter, this fails.
    """
    from temporalio.converter import DataConverter

    payload = _mset_payload(2_000)
    encoded = DataConverter.default.payload_converter.to_payloads([payload])[0]

    assert payload_size(payload) == len(encoded.data) + PAYLOAD_FRAMING_BYTES
    assert len(encoded.SerializeToString()) - len(encoded.data) == PAYLOAD_FRAMING_BYTES


def test_default_json_separators_would_overstate_the_payload() -> None:
    """Guards the specific mistake that produced a false verdict.

    Documented as a test because the failure mode is invisible: the naive measurement is
    ~10.5% high, which only matters near the limit -- exactly where MSET sits.
    """
    payload = _mset_payload(100_000)
    naive = len(json.dumps(payload).encode())
    assert naive > payload_size(payload)
    assert naive > TEMPORAL_DEFAULT_LIMIT_BYTES > payload_size(payload)


def test_submission_checks_policy_before_size() -> None:
    """The primary guard, at the boundary where the payload has not yet reached Temporal."""
    with pytest.raises(ValueError, match="cannot run through AsyncTask yet"):
        check_submission({"tool": "mset", "input": {"group_1_background": ["A"] * 10}})


def test_submission_allows_an_ordinary_request() -> None:
    """The ordinary path returns the measured size for logging."""
    payload = {"tool": "upset", "input": {"geneset_ids": [1, 2]}}
    assert check_submission(payload) == payload_size(payload)


class TestRequestShape:
    """`requested_tool` guards the workflow's first indexing operation.

    A malformed request used to raise `KeyError` from inside `@workflow.run`, which is not a
    `ValueError` and so escaped the non-retryable wrapper -- returning the run to Temporal's
    indefinite workflow-task retry. AsyncTask sees this plugin's schema as plain `dict`, so
    it does not reject such a request first.
    """

    def test_a_well_formed_request_yields_its_tool(self) -> None:
        """The ordinary path returns the tool name."""
        from geneweaver.tools.temporal.payload import requested_tool

        assert requested_tool({"tool": "upset", "input": {}}) == "upset"

    @pytest.mark.parametrize(
        "request_body",
        [
            {},
            {"input": {}},
            {"tool": None},
            {"tool": ""},
            {"tool": "   "},
            {"tool": 7},
            {"tool": ["upset"]},
        ],
        ids=["empty", "no-tool", "none", "blank", "whitespace", "int", "list"],
    )
    def test_a_malformed_request_raises_value_error(self, request_body: dict) -> None:
        """ValueError specifically -- that is what the workflow converts to non-retryable."""
        from geneweaver.tools.temporal.payload import requested_tool

        with pytest.raises(ValueError):
            requested_tool(request_body)

    @pytest.mark.parametrize("request_body", [None, "upset", 42, ["upset"]])
    def test_a_non_mapping_request_raises_value_error(self, request_body: object) -> None:
        """Not a dict at all -- indexing would have raised TypeError, also unwrapped."""
        from geneweaver.tools.temporal.payload import requested_tool

        with pytest.raises(ValueError, match="must be an object"):
            requested_tool(request_body)
