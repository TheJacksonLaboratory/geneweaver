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
    """AsyncTask refused a call or could not be reached.

    ``status_code`` is AsyncTask's HTTP status where there was one, so the endpoint can pass
    through an ownership refusal (403) or a missing run (404) rather than reporting every
    problem as an outage.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


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

    def _call(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(
                method, url, headers=self.headers, timeout=self.request_timeout, **kwargs
            )
        except requests.RequestException as error:
            raise AsyncTaskError(f"AsyncTask is unreachable ({method} {path}): {error}") from error
        if response.status_code >= 400:
            raise AsyncTaskError(
                f"AsyncTask refused {method} {path} with {response.status_code}: "
                f"{response.text[:500]}",
                status_code=response.status_code,
            )
        body = response.json()
        return body.get("object") or {}

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
        return RunState(
            run_id=run["id"],
            workflow_id=run.get("workflow_id"),
            status=status_name(run.get("status")),
        )

    def get(self, run_id: int) -> RunState:
        """A run's current status, with its result attached once it has completed."""
        run = self._call("GET", f"/runs/{run_id}")
        state = RunState(
            run_id=run_id,
            workflow_id=run.get("workflow_id"),
            status=status_name(run.get("status")),
        )
        if state.status == COMPLETED:
            state.result = self._call("GET", f"/runs/{run_id}/results").get("values")
        return state

    def wait(self, state: RunState, timeout: float, poll_interval: float) -> RunState:
        """Poll until the run finishes or `timeout` seconds pass, whichever is first.

        Returns the last state seen; a run still ``running`` at the deadline is not an
        error, the caller hands back its id instead.
        """
        deadline = time.monotonic() + timeout
        while not state.finished and time.monotonic() < deadline:
            time.sleep(poll_interval)
            state = self.get(state.run_id)
        return state
