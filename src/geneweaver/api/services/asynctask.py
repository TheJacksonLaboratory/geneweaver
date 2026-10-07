"""Client for AsyncTask's run API, used to execute tools out of process.

AsyncTask (`bitbucket.org/jacksonlaboratory/asynctask`) owns run state: it stores the run,
its owner and its status in its own database and executes it on Temporal, where the
`GeneWeaverTools` plugin's workflow routes each tool to our worker images. v3 therefore keeps
**no run table** (roadmap §4 guardrail 1) -- it submits, polls and reads back, and nothing
else.

Calls are made **as the user**, forwarding their bearer token. Both services validate the
same Auth0 tenant and audience, so the token v3 received is one AsyncTask accepts, and
AsyncTask's own ownership check (`run.owner_id != user.id` -> 403) is what stops one user
reading another's run. A run id is not an authorization control; this is.

The contract, read from AsyncTask's code rather than assumed:

* `POST /runs` with an `InputSubmission` body ``{task_type, name, values}``. Our plugin's
  input schema is a plain ``dict``, so ``values`` is the ``{"tool", "input"[, "universe"]}``
  envelope verbatim -- checked against AsyncTask's own model on dev, where a dict survives
  validation intact rather than being coerced into another plugin's input.
* `GET /runs/{id}` refreshes the run from Temporal and returns its status as Temporal's
  `WorkflowExecutionStatus` integer. Reaching COMPLETED is also what makes AsyncTask store
  the result, so it must be called before the result is read.
* `GET /runs/{id}/results` returns the stored result; its ``values`` are the workflow's
  return value, i.e. the tool's output.

AsyncTask exposes **no failure reason** -- a failed run is only a status. The workflow id is
returned so the cause can be found in Temporal.
"""

import time
from dataclasses import dataclass
from typing import Any

import requests

#: The plugin name AsyncTask registers `GeneWeaverToolWorkflow` under.
TASK_TYPE = "GeneWeaverTools"

#: Temporal's `WorkflowExecutionStatus` values, as AsyncTask serialises them.
STATUS_NAMES = {
    1: "running",
    2: "completed",
    3: "failed",
    4: "cancelled",
    5: "terminated",
    6: "continued_as_new",
    7: "timed_out",
}
RUNNING = "running"
COMPLETED = "completed"


class AsyncTaskError(RuntimeError):
    """AsyncTask refused a call, could not be reached, or answered outside its contract.

    ``status_code`` is AsyncTask's HTTP status where there was one, so the endpoint can pass
    through an ownership refusal (403) or a missing run (404) rather than reporting every
    problem as an outage.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AsyncTaskTimeout(AsyncTaskError):
    """A single call to AsyncTask ran out of time.

    Distinct so that `wait` can treat a slow *poll* as "still running" -- the run itself is
    unaffected -- while a slow *submission* is still an error.
    """


@dataclass
class RunState:
    """A run's identity and status, plus its output once it has completed."""

    run_id: int
    workflow_id: str | None
    status: str
    result: dict[str, Any] | None = None

    @property
    def finished(self) -> bool:
        """Whether the run has stopped, successfully or not."""
        return self.status != RUNNING


def status_name(value: Any) -> str:
    """Normalise AsyncTask's status to a lowercase name.

    Tolerates the enum's name as well as its integer, so a change in how AsyncTask
    serialises the enum does not turn every run into an unknown state.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return STATUS_NAMES.get(value, f"unknown({value})")
    return str(value).lower()


class AsyncTaskClient:
    """Submit a tool run to AsyncTask and read it back, as one user."""

    def __init__(
        self,
        base_url: str,
        token: str,
        request_timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        """Bind the client to an AsyncTask API root and a user's bearer token."""
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout
        self.session = session or requests.Session()
        self.headers = {"Authorization": f"Bearer {token}"}

    def _call(
        self, method: str, path: str, timeout: float | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Make one call and return the ``object`` of AsyncTask's response envelope.

        Everything that is not a well-formed envelope -- a transport failure, an error
        status, a non-JSON body (an ingress error page served as 200), or a body without a
        mapping under ``object`` -- is raised as an `AsyncTaskError`, so the endpoint reports
        an upstream fault (502) rather than crashing with a decoding error (500).
        """
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(
                method,
                url,
                headers=self.headers,
                timeout=self.request_timeout if timeout is None else timeout,
                **kwargs,
            )
        except requests.Timeout as error:
            raise AsyncTaskTimeout(f"AsyncTask timed out ({method} {path}): {error}") from error
        except requests.RequestException as error:
            raise AsyncTaskError(f"AsyncTask is unreachable ({method} {path}): {error}") from error
        if response.status_code >= 400:
            raise AsyncTaskError(
                f"AsyncTask refused {method} {path} with {response.status_code}: "
                f"{response.text[:500]}",
                status_code=response.status_code,
            )
        try:
            body = response.json()
        except ValueError as error:
            raise AsyncTaskError(
                f"AsyncTask answered {method} {path} with a body that is not JSON: "
                f"{response.text[:200]!r}"
            ) from error
        obj = body.get("object") if isinstance(body, dict) else None
        if not isinstance(obj, dict):
            raise AsyncTaskError(
                f"AsyncTask answered {method} {path} without an object in its response "
                f"envelope: {str(body)[:200]}"
            )
        return obj

    @staticmethod
    def _run_state(run: dict[str, Any], method: str, path: str) -> RunState:
        """Read a run out of AsyncTask's response, refusing one without an id or status."""
        run_id = run.get("id")
        if not isinstance(run_id, int) or isinstance(run_id, bool) or "status" not in run:
            raise AsyncTaskError(
                f"AsyncTask answered {method} {path} with a run missing its id or status: "
                f"{str(run)[:200]}"
            )
        return RunState(
            run_id=run_id,
            workflow_id=run.get("workflow_id"),
            status=status_name(run["status"]),
        )

    def submit(self, envelope: dict[str, Any], name: str) -> RunState:
        """Start a run of the `GeneWeaverTools` plugin.

        :param envelope: ``{"tool": ..., "input": {...}}``, optionally with ``"universe"``.
        :param name: A label for the run, shown in AsyncTask's own listings.
        """
        run = self._call(
            "POST",
            "/runs",
            json={"task_type": TASK_TYPE, "name": name, "values": envelope},
        )
        return self._run_state(run, "POST", "/runs")

    def get(self, run_id: int, timeout: float | None = None) -> RunState:
        """A run's current status, with its result attached once it has completed.

        :param timeout: A budget in seconds shared by both calls -- the result fetch gets only
            what the status check left -- overriding the client's per-call default.
        """
        started = time.monotonic()
        path = f"/runs/{run_id}"
        state = self._run_state(self._call("GET", path, timeout=timeout), "GET", path)
        if state.status == COMPLETED:
            result_path = f"{path}/results"
            left = None
            if timeout is not None:
                left = timeout - (time.monotonic() - started)
                if left <= 0:
                    raise AsyncTaskTimeout(f"No time left to fetch GET {result_path}.")
            values = self._call("GET", result_path, timeout=left).get("values")
            if not isinstance(values, dict):
                raise AsyncTaskError(
                    f"AsyncTask answered GET {result_path} without a result object: "
                    f"{str(values)[:200]}"
                )
            state.result = values
        return state

    def wait(self, state: RunState, timeout: float, poll_interval: float) -> RunState:
        """Poll until the run finishes or `timeout` seconds pass, whichever is first.

        The budget is a ceiling, not a target: sleeps are capped at what remains, nothing is
        polled once it is spent, and each poll's HTTP calls are bounded by the remainder. A
        poll that runs out of time returns the last state seen rather than raising -- the
        run is unaffected, so the caller hands back its id to poll later instead of
        reporting an outage.
        """
        deadline = time.monotonic() + timeout
        while not state.finished:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(poll_interval, remaining))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                state = self.get(state.run_id, timeout=min(self.request_timeout, remaining))
            except AsyncTaskTimeout:
                break
        return state
