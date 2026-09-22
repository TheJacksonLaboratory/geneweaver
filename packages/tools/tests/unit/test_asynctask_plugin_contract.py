"""The AsyncTask plugin contract for the GeneWeaver tools.

The AsyncTask service (``bitbucket.org/jacksonlaboratory/asynctask``) runs analysis work
as plugins. It discovers them through the ``jax.ats.plugins`` entry-point group with
``importlib.metadata``, wraps each in a facade, and rejects anything that does not
satisfy its ``AsyncTaskPlugin`` protocol.

AsyncTask is a separate, privately published service, so this module restates its
protocol locally rather than depending on it. These tests fail if a tool stops being
discoverable, stops loading, or stops conforming -- any of which would break the tools
in AsyncTask without breaking anything in this repository.

Note that a stale editable install will not carry newly declared entry points; the
failure message for that case says so, because the symptom is otherwise confusing.
"""

import importlib.metadata
from typing import Protocol, runtime_checkable

import pytest
from geneweaver.tools.framework import AbstractTool, ToolInput, ToolOutput

ENTRY_POINT_GROUP = "jax.ats.plugins"

#: Plugin name -> the class it must resolve to. Names are namespaced under
#: ``geneweaver.`` because AsyncTask's loader raises on duplicates across *every*
#: installed plugin, and ``geneweaver-boolean-algebra`` is already installed there.
EXPECTED_PLUGINS = {
    "geneweaver.boolean_algebra": "BooleanAlgebra",
    "geneweaver.combine": "Combine",
    "geneweaver.dbscan": "DBSCAN",
    "geneweaver.hypergeometric": "HyperGeometric",
    "geneweaver.jaccard_clustering": "JaccardClustering",
    "geneweaver.jaccard_similarity": "JaccardSimilarity",
    "geneweaver.mset": "MSET",
    "geneweaver.phenome_map": "PhenomeMap",
    "geneweaver.upset": "UpSet",
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
        for ep in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
        if ep.value.startswith("geneweaver.tools")
    }


@pytest.fixture(scope="module")
def entry_points() -> dict:
    """The declared entry points, skipping the module if the install is stale."""
    found = _declared_entry_points()
    if not found:
        pytest.skip(
            f"No {ENTRY_POINT_GROUP} entry points found for geneweaver-tools. The "
            "installed distribution metadata predates these entry points -- reinstall "
            "the workspace (`uv sync --all-packages --all-extras`) and re-run."
        )
    return found


def test_every_expected_tool_is_registered(entry_points: dict) -> None:
    """All nine canonical tools are discoverable by AsyncTask."""
    assert set(entry_points) == set(EXPECTED_PLUGINS)


def test_binary_dbscan_is_not_registered(entry_points: dict) -> None:
    """BinaryDBSCAN stays unregistered; it is the parity fallback, not the default."""
    assert not any(ep.value.endswith(":BinaryDBSCAN") for ep in entry_points.values())


def test_plugin_names_are_namespaced(entry_points: dict) -> None:
    """Names are namespaced so they cannot collide with other installed plugins."""
    unnamespaced = [name for name in entry_points if not name.startswith("geneweaver.")]
    assert not unnamespaced


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
