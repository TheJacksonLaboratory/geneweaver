"""What AsyncTask sees of this plugin: its entry points and the workflow it starts.

AsyncTask (``bitbucket.org/jacksonlaboratory/asynctask``) discovers plugins through
``jax.ats.plugins`` (the facade it validates) and ``jax.ats.plugins.temporal.workflows``
(what its worker registers). Its protocol is restated here rather than depended on, because
it is a separate, privately published service. A stale editable install will not carry
newly declared entry points; reinstall the workspace (`uv sync --all-packages`) if these
fail with nothing found.
"""

import importlib.metadata
import inspect

from geneweaver.tools_plugin import workflows
from geneweaver.tools_plugin.contract import ACTIVITY_NAME


def _ours(group: str) -> dict[str, str]:
    """This distribution's entry points in `group`, as name -> target."""
    return {
        ep.name: ep.value
        for ep in importlib.metadata.entry_points(group=group)
        if ep.value.startswith("geneweaver.tools")
    }


def test_asynctask_is_offered_the_workflow_only() -> None:
    """One plugin, the workflow -- AsyncTask passes it to `start_workflow`."""
    assert _ours("jax.ats.plugins") == {
        "GeneWeaverTools": "geneweaver.tools_plugin.workflows:GeneWeaverToolWorkflow"
    }


def test_asynctask_registers_the_workflow() -> None:
    """Its worker registers what this group returns, so it must resolve to the workflow."""
    declared = _ours("jax.ats.plugins.temporal.workflows")
    assert declared == {"GeneWeaverToolWorkflows": "geneweaver.tools_plugin.workflows:WORKFLOWS"}
    loaded = importlib.metadata.entry_points(group="jax.ats.plugins.temporal.workflows")
    (entry_point,) = [ep for ep in loaded if ep.name == "GeneWeaverToolWorkflows"]
    assert entry_point.load() == [workflows.GeneWeaverToolWorkflow]


def test_asynctask_registers_no_activity() -> None:
    """The activity runs on GeneWeaver's workers; AsyncTask must not load or register it.

    Registering it would put the code that runs a tool, and reads the GeneWeaver database,
    into AsyncTask's worker -- and the activities group is the only way in.
    """
    assert _ours("jax.ats.plugins.temporal.activities") == {}


def test_the_run_signature_satisfies_asynctask_schema_validation() -> None:
    """Reproduce AsyncTask's `Plugin.validate_schemas` exactly.

    It does ``inspect.signature(plugin.run).parameters["input_data"]`` and rejects either
    annotation being empty. A failure is caught by `load_plugins()` and logged, so the
    plugin is then **silently absent** from the registry. This caught a real defect once:
    the parameter was named `request`.
    """
    signature = inspect.signature(workflows.GeneWeaverToolWorkflow.run)
    assert "input_data" in signature.parameters
    assert signature.parameters["input_data"].annotation is not inspect.Parameter.empty
    assert signature.return_annotation is not inspect.Parameter.empty


def test_the_workflow_schedules_the_activity_by_name() -> None:
    """By name, so the workflow module needs nothing from the tools library."""
    source = inspect.getsource(workflows)
    assert "ACTIVITY_NAME," in source
    assert ACTIVITY_NAME == "geneweaver_run_tool"
    assert "geneweaver.tools." not in source.replace("geneweaver.tools_plugin", "")
