"""Tests for the bounded TOOLBOX binary runner."""

import subprocess
import sys

import pytest
from geneweaver.tools.framework.binary import (
    DEFAULT_TIMEOUT_SECONDS,
    TIMEOUT_ENV_VAR,
    binary_timeout,
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
