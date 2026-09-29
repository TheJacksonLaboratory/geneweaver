"""Running the TOOLBOX binaries with a bounded lifetime.

Several tools shell out to compiled binaries -- MSET to ``MSETcpp``, PhenomeMap to
``biclique`` and ``bstrap``, ``BinaryDBSCAN`` to ``dbscan``. None of them had a timeout,
which matters once the tools run as a Temporal activity:

Temporal's ``start_to_close_timeout`` marks an activity timed out, but it cannot interrupt
a blocking call in a worker thread or reap the child process that call is waiting on. A
hung binary therefore keeps a worker thread and a subprocess alive *after* the run has
been reported as timed out, and repeated hangs exhaust the worker pool. The bound has to
be enforced here, by the process that actually owns the child.

The default sits below the Temporal deadline so the child is killed first and the failure
is attributable to the tool rather than surfacing as an opaque activity timeout.

**Known limitation:** ``subprocess.run(timeout=...)`` kills the direct child, not its
descendants. None of the current TOOLBOX binaries spawn grandchildren; a binary that did
would need a process group kill instead.
"""

import os
import subprocess

#: Overrides the default, per the repository's rule that operational limits come from the
#: environment rather than being compiled in.
TIMEOUT_ENV_VAR = "GENEWEAVER_TOOL_BINARY_TIMEOUT"

#: Seconds. Below the 30-minute Temporal activity deadline in
#: ``geneweaver.tools.temporal.workflows``, so the child dies before the run is declared
#: timed out.
DEFAULT_TIMEOUT_SECONDS = 25 * 60


def binary_timeout() -> float:
    """Resolve the per-invocation timeout, falling back to the default.

    An unparseable or non-positive value falls back rather than failing the run: a bad
    environment variable should not take the tools down, and the default is safe.
    """
    raw = os.environ.get(TIMEOUT_ENV_VAR)
    if not raw:
        return float(DEFAULT_TIMEOUT_SECONDS)
    try:
        value = float(raw)
    except ValueError:
        return float(DEFAULT_TIMEOUT_SECONDS)
    return value if value > 0 else float(DEFAULT_TIMEOUT_SECONDS)


def run_binary(
    cmd: list[str],
    cwd: str | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    """Run a TOOLBOX binary, killing it if it outlives the timeout.

    :param cmd: The command and its arguments.
    :param cwd: Working directory for the child, if it matters.
    :param timeout: Seconds; defaults to :func:`binary_timeout`.
    :return: The completed process. Exit status is **not** checked -- callers raise their
        own errors, since each binary reports failure differently.
    :raises RuntimeError: If the binary exceeded the timeout and was killed.
    """
    limit = binary_timeout() if timeout is None else timeout
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=limit,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"{os.path.basename(cmd[0])} exceeded {limit:g}s and was killed. Either the "
            f"input is larger than this tool handles, or the binary is hung -- "
            f"{TIMEOUT_ENV_VAR} raises the limit if the run is legitimately long."
        ) from exc
