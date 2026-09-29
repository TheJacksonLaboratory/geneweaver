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

A timeout alone still leaves cancellation unhandled: Temporal delivers cancellation to an
activity, but a thread blocked in ``subprocess.run`` never observes it, so a cancelled run
holds a worker thread and a native child until the bound expires. So the wait is a poll loop
rather than a block, and :func:`progress_hook` lets the activity heartbeat and surrender on
cancellation. Tools call :func:`run_binary` without knowing any of this.

**Known limitation:** the child is terminated, not its descendants. None of the current
TOOLBOX binaries spawn grandchildren; a binary that did would need a process-group kill.
"""

import contextlib
import contextvars
import os
import subprocess
import time
from collections.abc import Callable, Iterator

#: Overrides the default, per the repository's rule that operational limits come from the
#: environment rather than being compiled in.
TIMEOUT_ENV_VAR = "GENEWEAVER_TOOL_BINARY_TIMEOUT"

#: The activity deadline this bound has to stay under -- `TOOL_RUN_TIMEOUT` in
#: ``geneweaver.tools.temporal.workflows`` is built from it. It lives here rather than there
#: so this module can cap against it without importing temporalio, which the tools must not
#: require just to run a binary.
TOOL_RUN_TIMEOUT_SECONDS = 30 * 60

#: Seconds of margin below the activity deadline, leaving room to collect the child's output
#: and report the failure before Temporal abandons the activity.
TIMEOUT_MARGIN_SECONDS = 5 * 60

#: The largest bound that still lets this process report the timeout itself.
MAX_TIMEOUT_SECONDS = TOOL_RUN_TIMEOUT_SECONDS - TIMEOUT_MARGIN_SECONDS

#: How often the wait loop checks on the child. Also the heartbeat cadence, so it must stay
#: well under any `heartbeat_timeout` the workflow sets.
POLL_INTERVAL_SECONDS = 1.0

#: Grace between `terminate()` and `kill()`, so a binary can flush and exit on SIGTERM.
TERMINATE_GRACE_SECONDS = 5.0

#: Called once per poll while a binary runs. Returning a truthy value asks for the run to be
#: abandoned; the child is then terminated and `RunCancelled` raised. A ContextVar rather
#: than a parameter because `run_binary` is called from inside the tools, which know nothing
#: about Temporal and should not have to thread this through.
_progress_hook: contextvars.ContextVar[Callable[[], bool] | None] = contextvars.ContextVar(
    "geneweaver_binary_progress_hook", default=None
)


class RunCancelled(RuntimeError):
    """Raised when a binary was abandoned because the caller asked for cancellation."""


@contextlib.contextmanager
def progress_hook(hook: Callable[[], bool]) -> Iterator[None]:
    """Install `hook` for the duration of the block.

    The activity uses this to heartbeat and to observe Temporal cancellation while a
    synchronous tool runs beneath it.
    """
    token = _progress_hook.set(hook)
    try:
        yield
    finally:
        _progress_hook.reset(token)


def _stop(process: subprocess.Popen) -> None:
    """End a child that is still running, escalating if it ignores SIGTERM."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


#: Seconds. Below the Temporal activity deadline, so the child dies before the run is
#: declared timed out.
DEFAULT_TIMEOUT_SECONDS = MAX_TIMEOUT_SECONDS


def binary_timeout() -> float:
    """Resolve the per-invocation timeout, falling back to the default.

    An unparseable or non-positive value falls back rather than failing the run: a bad
    environment variable should not take the tools down, and the default is safe. A value
    above :data:`MAX_TIMEOUT_SECONDS` is capped to it, for the reason given below.
    """
    raw = os.environ.get(TIMEOUT_ENV_VAR)
    if not raw:
        return float(DEFAULT_TIMEOUT_SECONDS)
    try:
        value = float(raw)
    except ValueError:
        return float(DEFAULT_TIMEOUT_SECONDS)
    if value <= 0:
        return float(DEFAULT_TIMEOUT_SECONDS)
    # Capped, not honoured as given: a bound at or above the activity deadline reinstates
    # exactly the failure this module exists to prevent -- Temporal abandons the activity
    # while the binary keeps a worker thread and its child alive. Raising the ceiling means
    # raising `TOOL_RUN_TIMEOUT` too, which is a workflow change, not configuration.
    return float(min(value, MAX_TIMEOUT_SECONDS))


def run_binary(
    cmd: list[str],
    cwd: str | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    """Run a TOOLBOX binary, killing it if it outlives the timeout or is cancelled.

    :param cmd: The command and its arguments.
    :param cwd: Working directory for the child, if it matters.
    :param timeout: Seconds; defaults to :func:`binary_timeout`.
    :return: The completed process. Exit status is **not** checked -- callers raise their
        own errors, since each binary reports failure differently.
    :raises RuntimeError: If the binary exceeded the timeout and was killed.
    :raises RunCancelled: If an installed :func:`progress_hook` asked to abandon the run.
    """
    limit = binary_timeout() if timeout is None else timeout
    hook = _progress_hook.get()
    started = time.monotonic()

    # Popen and poll rather than `subprocess.run(timeout=...)`: a blocking wait cannot
    # observe cancellation, and an activity that cannot be cancelled holds its worker
    # thread and this child until the bound expires.
    with subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    ) as process:
        while True:
            try:
                stdout, stderr = process.communicate(timeout=POLL_INTERVAL_SECONDS)
            except subprocess.TimeoutExpired:
                pass
            else:
                return subprocess.CompletedProcess(
                    cmd, process.returncode, stdout=stdout, stderr=stderr
                )

            elapsed = time.monotonic() - started
            if elapsed > limit:
                _stop(process)
                raise RuntimeError(
                    f"{os.path.basename(cmd[0])} exceeded {limit:g}s and was killed. Either "
                    f"the input is larger than this tool handles, or the binary is hung -- "
                    f"{TIMEOUT_ENV_VAR} raises the limit for a legitimately long run, up to "
                    f"{MAX_TIMEOUT_SECONDS:g}s."
                )

            if hook is not None and hook():
                _stop(process)
                raise RunCancelled(
                    f"{os.path.basename(cmd[0])} was cancelled after {elapsed:.0f}s "
                    f"and its process terminated."
                )
