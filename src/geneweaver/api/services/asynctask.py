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

* `POST /runs` with an `InputSubmission` body ``{task_type, name, values}``. ``values`` is
  the ``{"tool", "input"[, "universe" | "identity"]}`` envelope verbatim. AsyncTask parses
  it against the union of every plugin's input schema, whatever ``task_type`` says, so our
  plugin declares it as `geneweaver.tools_plugin.payload.ToolRequest`: as a bare ``dict`` it
  lost that union to the strain recommender's all-defaults model, and the workflow received
  that model instead of the request.
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
    #: When Temporal started the run (AsyncTask's ``init_time``, ISO 8601), if it said.
    init_time: str | None = None

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

    def _request(self, method: str, path: str, timeout: float | None = None, **kwargs: Any) -> Any:
        """Make one call and return its decoded JSON body.

        Everything that is not a JSON answer -- a transport failure, an error status, a
        non-JSON body (an ingress error page served as 200) -- is raised as an
        `AsyncTaskError`, so the endpoint reports an upstream fault (502) rather than
        crashing with a decoding error (500). The readers below check the envelope's shape.
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
            return response.json()
        except ValueError as error:
            raise AsyncTaskError(
                f"AsyncTask answered {method} {path} with a body that is not JSON: "
                f"{response.text[:200]!r}"
            ) from error

    def _call(
        self, method: str, path: str, timeout: float | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Make one call and return the mapping under ``object`` in AsyncTask's envelope.

        A body without one is an `AsyncTaskError`, like any other answer outside the
        contract.
        """
        body = self._request(method, path, timeout=timeout, **kwargs)
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
        init_time = run.get("init_time")
        return RunState(
            run_id=run_id,
            workflow_id=run.get("workflow_id"),
            status=status_name(run["status"]),
            init_time=init_time if isinstance(init_time, str) else None,
        )

    def submit(
        self, envelope: dict[str, Any], name: str, description: str | None = None
    ) -> RunState:
        """Start a run of the `GeneWeaverTools` plugin.

        :param envelope: ``{"tool": ..., "input": {...}}``, optionally with ``"universe"``.
        :param name: A label for the run, shown in AsyncTask's own listings.
        :param description: Stored by AsyncTask on the run's input and returned by
            ``GET /inputs``; v3 keeps the run's original request here (`run_record`).
        """
        body: dict[str, Any] = {"task_type": TASK_TYPE, "name": name, "values": envelope}
        if description is not None:
            body["description"] = description
        run = self._call("POST", "/runs", json=body)
        return self._run_state(run, "POST", "/runs")

    def _collection(self, path: str) -> list[dict[str, Any]]:
        """Make one GET and return the ``data`` list of AsyncTask's collection envelope.

        The list endpoints answer with ``CollectionResponse`` (``{data, paging, ...}``), not
        the ``object`` envelope `_call` reads.
        """
        body = self._request("GET", path)
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise AsyncTaskError(
                f"AsyncTask answered GET {path} without a list in its collection envelope: "
                f"{str(body)[:200]}"
            )
        return data

    def list_runs(self) -> list[dict[str, Any]]:
        """Every run of this user's, of every plugin, as AsyncTask stores them.

        AsyncTask refreshes each running one from Temporal first. Its ``?workflow_id=``
        filter is deliberately never used: at 5f2acea it returns the run without checking
        its owner.
        """
        return self._collection("/runs")

    def list_inputs(self) -> list[dict[str, Any]]:
        """Every input of this user's: ``{id, name, description}``, without the values."""
        return self._collection("/inputs")

    def get_run_input(self, run_id: int) -> dict[str, Any]:
        """The input a run was submitted with: ``{id, name, description, values, ...}``.

        Owner-checked by AsyncTask (403 for another user's run).
        """
        return self._call("GET", f"/runs/{run_id}/inputs")

    def get_status(self, run_id: int) -> RunState:
        """A run's status alone, never fetching its result (unlike `get`)."""
        path = f"/runs/{run_id}"
        return self._run_state(self._call("GET", path), "GET", path)

    def cancel(self, run_id: int) -> RunState:
        """Cancel a running run's workflow. AsyncTask answers 400 if it is not running."""
        path = f"/runs/{run_id}/cancel"
        return self._run_state(self._call("POST", path), "POST", path)

    def result_id(self, run_id: int) -> int | None:
        """The id of a run's stored result, or None if it has none (AsyncTask's 404)."""
        try:
            result = self._call("GET", f"/runs/{run_id}/results")
        except AsyncTaskError as error:
            if error.status_code == 404:
                return None
            raise
        result_id = result.get("id")
        if not isinstance(result_id, int) or isinstance(result_id, bool):
            raise AsyncTaskError(
                f"AsyncTask answered GET /runs/{run_id}/results with a result missing its id: "
                f"{str(result)[:200]}"
            )
        return result_id

    def delete_result(self, result_id: int) -> None:
        """Delete a stored result (owner-checked by AsyncTask through its run)."""
        self._call_bool("DELETE", f"/results/{result_id}")

    def delete_run(self, run_id: int) -> None:
        """Delete a run. AsyncTask refuses (400) while the run still has a result."""
        self._call_bool("DELETE", f"/runs/{run_id}")

    def _call_bool(self, method: str, path: str) -> None:
        """A call AsyncTask answers with ``Response[bool]``: ``object`` is a bare boolean.

        `_call` requires a mapping under ``object``, so these are read separately; anything
        but ``true`` is an error.
        """
        body = self._request(method, path)
        if not (isinstance(body, dict) and body.get("object") is True):
            raise AsyncTaskError(f"AsyncTask did not confirm {method} {path}: {str(body)[:200]}")

    def get(self, run_id: int, timeout: float | None = None) -> RunState:
        """A run's current status, with its result attached once it has completed.

        :param timeout: A budget in seconds shared by both calls -- the result fetch gets only
            what the status check left -- overriding the client's per-call default.
        """
        started = time.monotonic()
        path = f"/runs/{run_id}"
        state = self._run_state(self._call("GET", path, timeout=timeout), "GET", path)
        if state.status == COMPLETED:
            left = None
            if timeout is not None:
                left = timeout - (time.monotonic() - started)
                if left <= 0:
                    raise AsyncTaskTimeout(f"No time left to fetch GET {path}/results.")
            state.result = self.get_result(run_id, timeout=left)
        return state

    def get_result(self, run_id: int, timeout: float | None = None) -> dict[str, Any]:
        """A completed run's output: the ``values`` of its stored result.

        AsyncTask stores the result when it first sees the run COMPLETED, which its
        ``GET /runs/{id}/results`` also checks, so this is safe to call on its own once a
        status read has said completed.
        """
        result_path = f"/runs/{run_id}/results"
        values = self._call("GET", result_path, timeout=timeout).get("values")
        if not isinstance(values, dict):
            raise AsyncTaskError(
                f"AsyncTask answered GET {result_path} without a result object: "
                f"{str(values)[:200]}"
            )
        return values

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
