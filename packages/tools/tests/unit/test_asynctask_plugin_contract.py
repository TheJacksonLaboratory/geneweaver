"""The AsyncTask plugin contract for the GeneWeaver tools.

The AsyncTask service (``bitbucket.org/jacksonlaboratory/asynctask``) runs analysis work
as plugins, discovered through three entry-point groups with ``importlib.metadata``:
``jax.ats.plugins`` for the facade, and ``jax.ats.plugins.temporal.{workflows,activities}``
for what its Temporal worker registers. This package declares all three itself, the way
``strain-recommendation`` does, so nothing GeneWeaver-specific lives in AsyncTask.

Separately, ``geneweaver.tools`` is *our* registry of runnable tools. It is deliberately
not ``jax.ats.plugins``: AsyncTask hands whatever it finds in that group to
``start_workflow``, which accepts only a Temporal workflow, so registering bare
``AbstractTool`` classes there would look right and fail at run time.

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

TOOL_GROUP = "geneweaver.tools"

#: Plugin name -> the class it must resolve to. Names are namespaced under
#: ``geneweaver.`` because AsyncTask's loader raises on duplicates across *every*
#: installed plugin, and ``geneweaver-boolean-algebra`` is already installed there.
EXPECTED_PLUGINS = {
    "boolean_algebra": "BooleanAlgebra",
    "combine": "Combine",
    "dbscan": "DBSCAN",
    "hypergeometric": "HyperGeometric",
    "jaccard_clustering": "JaccardClustering",
    "jaccard_similarity": "JaccardSimilarity",
    "mset": "MSET",
    "phenome_map": "PhenomeMap",
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
    """All nine canonical tools are discoverable by AsyncTask."""
    assert set(entry_points) == set(EXPECTED_PLUGINS)


def test_binary_dbscan_is_not_registered(entry_points: dict) -> None:
    """BinaryDBSCAN stays unregistered; it is the parity fallback, not the default."""
    assert not any(ep.value.endswith(":BinaryDBSCAN") for ep in entry_points.values())


def test_tools_are_not_registered_directly_with_asynctask() -> None:
    """Bare tools must not appear in `jax.ats.plugins`.

    AsyncTask passes entries from that group to `start_workflow`, which accepts only a
    Temporal workflow. A tool registered there would be discovered and then fail when
    run. Only the workflow belongs in that group.
    """
    registered = {
        ep.name: ep.value
        for ep in importlib.metadata.entry_points(group="jax.ats.plugins")
        if ep.value.startswith("geneweaver.tools")
    }
    assert registered == {
        "GeneWeaverTools": "geneweaver.tools.temporal.workflows:GeneWeaverToolWorkflow"
    }


def test_temporal_entry_points_are_declared() -> None:
    """The worker registers what these groups return, so they must resolve."""
    for group, expected in (
        ("jax.ats.plugins.temporal.workflows", "geneweaver.tools.temporal:WORKFLOWS"),
        ("jax.ats.plugins.temporal.activities", "geneweaver.tools.temporal:ACTIVITIES"),
    ):
        declared = {
            ep.name: ep.value
            for ep in importlib.metadata.entry_points(group=group)
            if ep.value.startswith("geneweaver.tools")
        }
        assert expected in declared.values(), f"{group} missing {expected}"


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
