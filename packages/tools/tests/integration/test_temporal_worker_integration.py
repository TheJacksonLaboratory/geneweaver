"""End-to-end test against a real Temporal server.

Covers two failures that unit tests cannot see:

* The worker could not start at all -- ``run_tool`` is synchronous and Temporal requires an
  ``activity_executor``. Asserting the contents of ``ACTIVITIES`` did not reveal it.
* A validation error raised inside ``@workflow.run`` must *fail* the run. A plain exception
  there puts Temporal into indefinite workflow-task retry, so the run hangs instead of
  failing -- the G3-739 symptom. Only a real server distinguishes the two.

Written as one synchronous test driving its own event loop, rather than async fixtures: the
server and worker are expensive to start, and module-scoped async fixtures depend on
pytest-asyncio loop-scope behaviour that changes between releases.

Skipped when the Temporal dev server cannot be started, so a sandboxed CI run does not fail.
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

os.environ.setdefault("GENEWEAVER_TOOLS_PROFILE", "python")

#: Bounds the "hung workflow" case: a non-retryable failure returns immediately, while the
#: bug this guards against would sit here until the test timed out.
BAD_REQUEST_TIMEOUT_SECONDS = 30

BAD_REQUESTS = [
    ({"input": {}}, "must name a tool"),
    ({"tool": ""}, "must name a tool"),
    # Input the tool's own schema rejects, exercising the activity's translation of a
    # pydantic ValidationError into a non-retryable failure. Uses a python-profile tool
    # deliberately: `mset` routes to the native queue, which this test does not serve, so
    # it would sit on `schedule_to_start_timeout` instead of failing on its input.
    ({"tool": "upset", "input": {"geneset_ids": "not-a-list"}}, "rejected its input"),
    ({"tool": "nonexistent", "input": {}}, "No GeneWeaver tool registered"),
]


def _causes(error: BaseException) -> list[BaseException]:
    """The exception and everything it was caused by, outermost first."""
    chain: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__
    return chain


async def _exercise() -> list[str]:
    """Start the real two-worker topology, then run one good request and the bad ones.

    Mirrors production rather than simplifying it:

    * an **orchestration** worker on a separate queue registering `WORKFLOWS` only --
      standing in for AsyncTask's worker, which is where the plugin's workflow runs;
    * our **compute** worker on `geneweaver-tools` registering `ACTIVITIES` only, exactly
      as `temporal.worker` builds it.

    So this also checks the cross-queue routing: the workflow is started on one queue and
    its activity has to be picked up on another. A single worker registering both would
    have passed even if `task_queue_for` were wrong.
    """
    from geneweaver.tools.temporal import ACTIVITIES, WORKFLOWS
    from geneweaver.tools.temporal.routing import PYTHON_TASK_QUEUE
    from temporalio.client import WorkflowFailureError
    from temporalio.testing import WorkflowEnvironment
    from temporalio.worker import Worker

    workflow = WORKFLOWS[0]
    orchestration_queue = "asynctask-stand-in"
    findings: list[str] = []

    try:
        env = await WorkflowEnvironment.start_local()
    except Exception as exc:
        pytest.skip(f"Temporal dev server unavailable: {type(exc).__name__}: {exc}")

    async with env:
        with ThreadPoolExecutor(max_workers=4) as executor:
            async with (
                Worker(
                    env.client,
                    task_queue=orchestration_queue,
                    workflows=WORKFLOWS,
                ),
                Worker(
                    env.client,
                    task_queue=PYTHON_TASK_QUEUE,
                    activities=ACTIVITIES,
                    activity_executor=executor,
                    max_concurrent_activities=4,
                ),
            ):
                result = await env.client.execute_workflow(
                    workflow.run,
                    {
                        "tool": "upset",
                        "input": {
                            "geneset_ids": ["1", "2"],
                            "gene_memberships": {"1": ["a", "b"], "2": ["b", "c"]},
                        },
                    },
                    id="integration-upset",
                    task_queue=orchestration_queue,
                )
                if "intersections" not in result:
                    findings.append(f"upset returned no intersections: {sorted(result)}")
                if [str(gid) for gid in result.get("geneset_ids", [])] != ["1", "2"]:
                    findings.append(f"unexpected geneset_ids: {result.get('geneset_ids')}")

                for index, (request, expected) in enumerate(BAD_REQUESTS):
                    try:
                        await asyncio.wait_for(
                            env.client.execute_workflow(
                                workflow.run,
                                request,
                                id=f"integration-bad-{index}",
                                task_queue=orchestration_queue,
                            ),
                            timeout=BAD_REQUEST_TIMEOUT_SECONDS,
                        )
                    except TimeoutError:
                        findings.append(
                            f"{request} did not fail within "
                            f"{BAD_REQUEST_TIMEOUT_SECONDS}s -- the workflow task is being "
                            "retried instead of failing"
                        )
                    except WorkflowFailureError as error:
                        reason = " | ".join(str(cause) for cause in _causes(error))
                        if expected not in reason:
                            findings.append(f"{request} failed with: {reason[:200]}")
                    else:
                        findings.append(f"{request} unexpectedly succeeded")

    return findings


def test_the_worker_starts_and_runs_tools_against_a_real_server() -> None:
    """One test, because the server and worker are shared setup for every assertion."""
    findings = asyncio.run(_exercise())
    assert not findings, "\n".join(findings)
