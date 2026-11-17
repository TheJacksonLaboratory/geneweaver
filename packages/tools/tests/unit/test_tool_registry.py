"""The `geneweaver.tools` registry: the tools the worker's activity can load by name.

It is our own entry-point group, deliberately not ``jax.ats.plugins``: AsyncTask hands
whatever it finds in that group to ``start_workflow``, which accepts only a Temporal
workflow. And since the workflow moved to ``geneweaver-tools-plugin``, this package offers
AsyncTask nothing at all -- AsyncTask installs the plugin, never the tools.

Each tool still satisfies AsyncTask's runtime-checkable plugin protocol (a ``run``) and
declares its input and output schemas, which is the framework contract the activity relies
on. A stale editable install will not carry newly declared entry points; the failure message
for that case says so, because the symptom is otherwise confusing.
"""

import importlib.metadata
from typing import Protocol, runtime_checkable

import pytest
from geneweaver.tools.framework import AbstractTool, ToolInput, ToolOutput

TOOL_GROUP = "geneweaver.tools"

#: Tool name -> the class it must resolve to, in the **private** ``geneweaver.tools``
#: group. Plain names, not namespaced: this group is read by our own activity, never by
#: AsyncTask.
EXPECTED_PLUGINS = {
    "boolean_algebra": "BooleanAlgebra",
    "combine": "Combine",
    "dbscan": "DBSCAN",
    "geneset_graph": "GenesetGraph",
    "hypergeometric": "HyperGeometric",
    "jaccard_clustering": "JaccardClustering",
    "jaccard_similarity": "JaccardSimilarity",
    "mset": "MSET",
    "phenome_map": "PhenomeMap",
    "triclique": "TricliqueTool",
    "upset": "UpSet",
}


@runtime_checkable
class AsyncTaskPlugin(Protocol):
    """Mirror of ``asynctask.plugins.protocols.AsyncTaskPlugin`` (asynctask 0.6.0a1).

    Kept deliberately minimal: AsyncTask's protocol is ``runtime_checkable``, so
    conformance is decided by the presence of ``run``, not by its annotations.
    """

    def run(self, input_data):
        """Run the plugin against its input and return its output."""


def _declared_entry_points() -> dict:
    """Return this distribution's ``jax.ats.plugins`` entry points, keyed by name."""
    return {
        ep.name: ep
        for ep in importlib.metadata.entry_points(group=TOOL_GROUP)
        if ep.value.startswith("geneweaver.tools")
    }


@pytest.fixture(scope="module")
def entry_points() -> dict:
    """The declared entry points, skipping the module if the install is stale."""
    found = _declared_entry_points()
    if not found:
        pytest.skip(
            f"No {TOOL_GROUP} entry points found for geneweaver-tools. The "
            "installed distribution metadata predates these entry points -- reinstall "
            "the workspace (`uv sync --all-packages --all-extras`) and re-run."
        )
    return found


def test_every_expected_tool_is_registered(entry_points: dict) -> None:
    """All eleven canonical tools are discoverable by the GeneWeaver activity."""
    assert set(entry_points) == set(EXPECTED_PLUGINS)


def test_binary_dbscan_is_not_registered(entry_points: dict) -> None:
    """BinaryDBSCAN stays unregistered; it is the parity fallback, not the default."""
    assert not any(ep.value.endswith(":BinaryDBSCAN") for ep in entry_points.values())


@pytest.mark.parametrize(
    "group",
    [
        "jax.ats.plugins",
        "jax.ats.plugins.temporal.workflows",
        "jax.ats.plugins.temporal.activities",
    ],
)
def test_this_package_offers_asynctask_nothing(group: str) -> None:
    """AsyncTask's entry points are the plugin's alone.

    AsyncTask depends on the plugin, not the tools. A `geneweaver.tools.*` target here would
    mean AsyncTask has to install this package and its scientific libraries again.
    """
    ours = [
        ep.value
        for ep in importlib.metadata.entry_points(group=group)
        if ep.value.startswith("geneweaver.tools.")
    ]
    assert ours == []


@pytest.mark.parametrize("name", sorted(EXPECTED_PLUGINS))
def test_plugin_loads_to_the_expected_tool(name: str, entry_points: dict) -> None:
    """Each entry point resolves to the tool class it claims."""
    loaded = entry_points[name].load()
    assert loaded.__name__ == EXPECTED_PLUGINS[name]


@pytest.mark.parametrize("name", sorted(EXPECTED_PLUGINS))
def test_plugin_is_an_abstract_tool(name: str, entry_points: dict) -> None:
    """Each plugin is a concrete AbstractTool, so the framework contract holds."""
    loaded = entry_points[name].load()
    assert issubclass(loaded, AbstractTool)


@pytest.mark.parametrize("name", sorted(EXPECTED_PLUGINS))
def test_plugin_satisfies_the_asynctask_protocol(name: str, entry_points: dict) -> None:
    """Each plugin instance satisfies AsyncTask's runtime-checkable protocol."""
    tool = entry_points[name].load()()
    assert isinstance(tool, AsyncTaskPlugin)


@pytest.mark.parametrize("name", sorted(EXPECTED_PLUGINS))
def test_plugin_declares_its_input_and_output_types(name: str, entry_points: dict) -> None:
    """Each plugin exposes the schemas AsyncTask needs to validate a submission."""
    tool = entry_points[name].load()()
    assert issubclass(tool.tool_input, ToolInput)
    assert issubclass(tool.tool_output, ToolOutput)
