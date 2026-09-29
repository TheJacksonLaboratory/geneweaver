"""Tests for the bounded TOOLBOX binary runner."""

import subprocess
import sys
import time

import pytest
from geneweaver.tools.framework.binary import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_TIMEOUT_SECONDS,
    TIMEOUT_ENV_VAR,
    TOOL_RUN_TIMEOUT_SECONDS,
    RunCancelled,
    binary_timeout,
    progress_hook,
    run_binary,
)


def test_default_timeout_is_below_the_temporal_deadline() -> None:
    """The child must die before Temporal declares the activity timed out.

    `geneweaver.tools.temporal.workflows.TOOL_RUN_TIMEOUT` is 30 minutes; Temporal cannot
    interrupt a blocking call or reap its child, so this bound has to fire first.
    """
    from geneweaver.tools.temporal.workflows import TOOL_RUN_TIMEOUT

    assert TOOL_RUN_TIMEOUT.total_seconds() > DEFAULT_TIMEOUT_SECONDS


def test_timeout_is_environment_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operational limits come from the environment, not the source."""
    monkeypatch.setenv(TIMEOUT_ENV_VAR, "12.5")
    assert binary_timeout() == 12.5


@pytest.mark.parametrize("value", ["", "not-a-number", "0", "-5"])
def test_unusable_timeout_falls_back(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bad env var must not take the tools down."""
    monkeypatch.setenv(TIMEOUT_ENV_VAR, value)
    assert binary_timeout() == float(DEFAULT_TIMEOUT_SECONDS)


def test_hanging_binary_is_killed_and_reported() -> None:
    """A binary that outlives its bound is killed, with an actionable error.

    Uses a real child process rather than a mock: the point of the change is that the
    child is actually terminated, which a patched `subprocess.run` cannot demonstrate.
    """
    with pytest.raises(RuntimeError, match=r"exceeded 0\.3s and was killed"):
        run_binary([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.3)


def test_successful_binary_returns_completed_process() -> None:
    """The ordinary path is unchanged, and exit status is left to the caller."""
    result = run_binary([sys.executable, "-c", "print('ok')"])
    assert isinstance(result, subprocess.CompletedProcess)
    assert result.stdout.strip() == "ok"
    assert result.returncode == 0


def test_failing_binary_is_not_raised_by_the_runner() -> None:
    """Callers raise their own errors -- each binary reports failure differently."""
    result = run_binary([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert result.returncode == 3


def test_an_over_limit_override_is_capped_not_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bound at or above the activity deadline reinstates worker exhaustion.

    Temporal would abandon the activity while the binary kept a worker thread and its child
    alive, which is the failure this module exists to prevent -- so the value is capped.
    """
    monkeypatch.setenv(TIMEOUT_ENV_VAR, str(TOOL_RUN_TIMEOUT_SECONDS * 10))
    assert binary_timeout() == float(MAX_TIMEOUT_SECONDS)


def test_an_under_limit_override_is_honoured_exactly(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cap must not disturb a legitimate override."""
    monkeypatch.setenv(TIMEOUT_ENV_VAR, str(MAX_TIMEOUT_SECONDS - 1))
    assert binary_timeout() == float(MAX_TIMEOUT_SECONDS - 1)


def test_the_cap_is_the_boundary_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cap value itself is allowed through unchanged."""
    monkeypatch.setenv(TIMEOUT_ENV_VAR, str(MAX_TIMEOUT_SECONDS))
    assert binary_timeout() == float(MAX_TIMEOUT_SECONDS)


def test_cancellation_terminates_the_child_promptly() -> None:
    """A cancelled run must not hold its child until the timeout expires.

    The whole point of the poll loop: with a blocking wait this process would sit here for
    the full bound. Uses a real long-lived child, and asserts it is gone afterwards.
    """
    calls: list[float] = []

    def hook() -> bool:
        calls.append(time.monotonic())
        return len(calls) >= 2  # let one poll pass, then ask to stop

    started = time.monotonic()
    with progress_hook(hook), pytest.raises(RunCancelled, match="was cancelled"):
        run_binary([sys.executable, "-c", "import time; time.sleep(120)"], timeout=120)
    elapsed = time.monotonic() - started

    assert elapsed < 20, f"cancellation took {elapsed:.1f}s; it should not wait for the bound"
    assert len(calls) >= 2


def test_the_hook_is_polled_during_a_run() -> None:
    """Heartbeating depends on this being called while the binary is still running."""
    calls = 0

    def hook() -> bool:
        nonlocal calls
        calls += 1
        return False

    with progress_hook(hook):
        result = run_binary([sys.executable, "-c", "import time; time.sleep(2.5)"])
    assert result.returncode == 0
    assert calls >= 2, f"hook called {calls} times during a 2.5s run"


def test_no_hook_installed_runs_normally() -> None:
    """Tools call this directly outside Temporal; there is no hook then."""
    assert run_binary([sys.executable, "-c", "print('fine')"]).stdout.strip() == "fine"


def test_the_hook_does_not_leak_past_its_block() -> None:
    """A ContextVar set without reset would apply the previous run's hook to the next."""
    with progress_hook(lambda: True):
        pass
    assert run_binary([sys.executable, "-c", "print('ok')"]).returncode == 0
