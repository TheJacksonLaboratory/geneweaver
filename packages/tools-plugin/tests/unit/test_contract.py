"""The names the workflow and the workers share, and the routing built on them.

These values are an agreement with deployed workers: changing one is a planned release of
this package and the workers together, not a refactor. `geneweaver-tools`' own contract test
checks the workers against them.
"""

import pytest
from geneweaver.tools_plugin.contract import (
    ACTIVITY_NAME,
    NATIVE_TASK_QUEUE,
    NATIVE_TOOLS,
    PYTHON_TASK_QUEUE,
    TOOL_RUN_TIMEOUT_SECONDS,
    task_queue_for,
)


def test_the_agreed_names() -> None:
    """Pinned: the deployed workers listen on these and register this activity."""
    assert PYTHON_TASK_QUEUE == "geneweaver-tools"
    assert NATIVE_TASK_QUEUE == "geneweaver-tools-native"
    assert ACTIVITY_NAME == "geneweaver_run_tool"
    assert TOOL_RUN_TIMEOUT_SECONDS == 30 * 60


def test_the_native_tools_are_mset_and_phenome_map() -> None:
    """The two tools that need compiled binaries, and so the native image."""
    assert {"mset", "phenome_map"} == NATIVE_TOOLS


@pytest.mark.parametrize("tool", sorted(NATIVE_TOOLS))
def test_native_tools_route_to_the_native_queue(tool: str) -> None:
    """Only the native image has the TOOLBOX binaries."""
    assert task_queue_for(tool) == NATIVE_TASK_QUEUE


@pytest.mark.parametrize(
    "tool",
    [
        "boolean_algebra",
        "combine",
        "dbscan",
        "hypergeometric",
        "jaccard_clustering",
        "jaccard_similarity",
        "upset",
        "abba",
    ],
)
def test_every_other_tool_routes_to_the_python_queue(tool: str) -> None:
    """DBSCAN too: its in-process implementation is the default, the binary a fallback."""
    assert task_queue_for(tool) == PYTHON_TASK_QUEUE


def test_an_unknown_tool_routes_to_the_python_queue() -> None:
    """Where the worker refuses it with the list of tools it knows, rather than hanging."""
    assert task_queue_for("nonexistent") == PYTHON_TASK_QUEUE
