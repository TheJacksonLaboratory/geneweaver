"""Tests for tool-to-worker routing.

The split is operational, not cosmetic: routing a native tool to the Python worker fails
with a missing-binary error that says nothing about queues, and routing to a queue with no
worker deployed looks exactly like a slow run.
"""

import pytest
from geneweaver.tools.temporal import routing
from geneweaver.tools.temporal.activities import available_tools
from geneweaver.tools.temporal.routing import (
    NATIVE_PROFILE,
    NATIVE_TASK_QUEUE,
    NATIVE_TOOLS,
    PYTHON_PROFILE,
    PYTHON_TASK_QUEUE,
    check_tool_served_here,
    current_profile,
    profile_for,
    task_queue_for,
    tools_for_profile,
)

NATIVE = ["mset", "phenome_map"]


def test_the_two_profiles_partition_every_registered_tool() -> None:
    """No tool may be unroutable, and none may be served by both workers."""
    tools = available_tools()
    python = tools_for_profile(PYTHON_PROFILE, tools)
    native = tools_for_profile(NATIVE_PROFILE, tools)

    assert sorted(python + native) == sorted(tools)
    assert not set(python) & set(native)


def test_the_split_is_seven_and_two() -> None:
    """Pins the profile membership the two images are built around."""
    tools = available_tools()
    assert len(tools_for_profile(PYTHON_PROFILE, tools)) == 7
    assert tools_for_profile(NATIVE_PROFILE, tools) == NATIVE


@pytest.mark.parametrize("tool", NATIVE)
def test_native_tools_route_to_the_native_queue(tool: str) -> None:
    """MSET and PhenomeMap only run where the TOOLBOX binaries are."""
    assert task_queue_for(tool) == NATIVE_TASK_QUEUE
    assert profile_for(tool) == NATIVE_PROFILE


def test_dbscan_is_a_python_tool_despite_having_a_binary() -> None:
    """Its in-process implementation is the default; the binary is the parity fallback.

    Putting it in the native profile would drag a build toolchain in for a tool whose
    canonical path does not need one.
    """
    assert task_queue_for("dbscan") == PYTHON_TASK_QUEUE
    assert "dbscan" not in NATIVE_TOOLS


def test_an_unknown_tool_routes_to_the_python_queue() -> None:
    """A new pure-Python tool should work without touching routing.

    Native tools are the exception and are listed explicitly, so the default is the one
    that needs no image change.
    """
    assert task_queue_for("some_future_tool") == PYTHON_TASK_QUEUE


def test_queue_names_are_environment_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Infrastructure is configuration; the names are resolved once at import."""
    monkeypatch.setattr(routing, "PYTHON_TASK_QUEUE", "custom-queue")
    assert routing.task_queue_for("upset") == "custom-queue"


def test_a_misrouted_tool_is_refused_with_the_queue_named() -> None:
    """The error has to be actionable: which worker, and which queue it should have used."""
    with pytest.raises(ValueError) as excinfo:
        check_tool_served_here("mset", profile=PYTHON_PROFILE)
    message = str(excinfo.value)
    assert "mset" in message
    assert NATIVE_TASK_QUEUE in message
    assert NATIVE_PROFILE in message


def test_a_correctly_routed_tool_is_accepted() -> None:
    """The ordinary path raises nothing."""
    check_tool_served_here("mset", profile=NATIVE_PROFILE)
    check_tool_served_here("upset", profile=PYTHON_PROFILE)


@pytest.mark.parametrize("value", ["", "  ", "pythonic", "PYTHON_NATIVE", "both"])
def test_an_unusable_profile_refuses_to_start(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fatal rather than defaulted.

    A worker that guessed `python` would advertise MSET and PhenomeMap and fail every run
    with a missing-binary error -- much harder to diagnose than refusing to start.
    """
    monkeypatch.setenv(routing.PROFILE_ENV_VAR, value)
    with pytest.raises(ValueError, match=routing.PROFILE_ENV_VAR):
        current_profile()


@pytest.mark.parametrize(("value", "expected"), [("python", "python"), ("NATIVE", "native")])
def test_the_profile_is_read_case_insensitively(
    value: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Operators should not be tripped by casing in a ConfigMap."""
    monkeypatch.setenv(routing.PROFILE_ENV_VAR, value)
    assert current_profile() == expected


def test_an_unset_profile_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing is as fatal as wrong -- there is no safe guess."""
    monkeypatch.delenv(routing.PROFILE_ENV_VAR, raising=False)
    with pytest.raises(ValueError):
        current_profile()
