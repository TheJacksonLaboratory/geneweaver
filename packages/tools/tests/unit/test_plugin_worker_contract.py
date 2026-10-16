"""The workers against the plugin: the agreement that joins two separate releases.

The workflow (`geneweaver-tools-plugin`, inside AsyncTask) and the workers (this package's
`temporal` extra, in GeneWeaver's two images) are deployed separately. They meet on a task
queue, an activity name, a deadline and the shape of a request. The workers import the
plugin's names rather than restating them; these tests fail if either side changes one
without the other -- a rename that would otherwise only show as runs that never start.
"""

import pytest
from geneweaver.tools.abba import TOOL_NAME as ABBA
from geneweaver.tools.framework import binary
from geneweaver.tools.temporal import ACTIVITIES, run_tool
from geneweaver.tools.temporal.activities import DATABASE_TOOLS, available_tools
from geneweaver.tools.temporal.routing import (
    PROFILES,
    QUEUE_FOR_PROFILE,
    check_tool_served_here,
    profile_for,
)
from geneweaver.tools.temporal.worker import task_queue
from geneweaver.tools_plugin import contract
from geneweaver.tools_plugin.payload import requested_tool


def test_the_worker_registers_the_activity_the_workflow_schedules() -> None:
    """The workflow schedules by name; a worker under another name never picks it up."""
    names = [activity.__temporal_activity_definition.name for activity in ACTIVITIES]
    assert names == [contract.ACTIVITY_NAME]


def test_the_two_workers_listen_on_the_plugins_two_queues() -> None:
    """One queue per profile, and exactly the queues the workflow sends to."""
    assert {task_queue(profile) for profile in PROFILES} == {
        contract.PYTHON_TASK_QUEUE,
        contract.NATIVE_TASK_QUEUE,
    }
    assert set(QUEUE_FOR_PROFILE.values()) == {
        contract.PYTHON_TASK_QUEUE,
        contract.NATIVE_TASK_QUEUE,
    }


@pytest.mark.parametrize("tool", [*available_tools(), *DATABASE_TOOLS])
def test_every_tool_is_sent_to_the_worker_that_serves_it(tool: str) -> None:
    """For each tool, the queue the workflow picks is the queue of the worker that runs it."""
    worker_profile = profile_for(tool)
    assert task_queue(worker_profile) == contract.task_queue_for(tool)
    check_tool_served_here(tool, profile=worker_profile)


def test_abba_needs_no_plugin_change() -> None:
    """A database tool the plugin has never heard of still routes to the python worker."""
    assert ABBA in DATABASE_TOOLS
    assert contract.task_queue_for(ABBA) == contract.PYTHON_TASK_QUEUE


def test_binaries_are_capped_against_the_workflows_deadline() -> None:
    """The binary bound sits under the workflow's deadline, from a restated constant.

    `framework.binary` restates the deadline because the tools must not depend on the
    plugin. A binary allowed to outlive the activity keeps its worker thread after Temporal
    has given up on it.
    """
    assert binary.TOOL_RUN_TIMEOUT_SECONDS == contract.TOOL_RUN_TIMEOUT_SECONDS
    assert binary.MAX_TIMEOUT_SECONDS < contract.TOOL_RUN_TIMEOUT_SECONDS


def test_the_activity_reads_requests_the_workflow_accepts() -> None:
    """The workflow accepts `{"tool", "input"}`; the activity runs exactly that."""
    request = {
        "tool": "upset",
        "input": {"geneset_ids": ["1", "2"], "gene_memberships": {"1": ["a"], "2": ["a"]}},
    }
    assert requested_tool(request) == "upset"
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("GENEWEAVER_TOOLS_PROFILE", "python")
        assert "intersections" in run_tool(request)


def test_the_activity_applies_the_plugins_size_guard() -> None:
    """Refused on size before the tool is loaded, with the plugin's message."""
    oversized = {"tool": "upset", "input": {"geneset_ids": ["x" * 64] * 40_000}}
    with pytest.MonkeyPatch.context() as patch, pytest.raises(ValueError, match="over the"):
        patch.setenv("GENEWEAVER_TOOLS_PROFILE", "python")
        run_tool(oversized)
