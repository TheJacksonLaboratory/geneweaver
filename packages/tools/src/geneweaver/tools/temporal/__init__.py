"""Temporal bindings so the tools can run on the AsyncTask service.

Mirrors ``strainrecommend.temporal``: the plugin package owns its own workflow,
activities and entry points, so nothing GeneWeaver-specific has to live in AsyncTask.

Requires the ``temporal`` extra (``geneweaver-tools[temporal]``); importing this package
without ``temporalio`` installed raises ImportError. Callers that only need the compute
classes and their schemas -- the GeneWeaver API, for one -- never import it.
"""

from .activities import available_tools, load_tool, run_tool
from .workflows import GeneWeaverToolWorkflow

#: Discovered by `asynctask.plugins.temporal.discover_workflow_plugins`.
WORKFLOWS = [GeneWeaverToolWorkflow]

#: Discovered by `asynctask.plugins.temporal.discover_activity_plugins`.
ACTIVITIES = [run_tool]

__all__ = [
    "ACTIVITIES",
    "WORKFLOWS",
    "GeneWeaverToolWorkflow",
    "available_tools",
    "load_tool",
    "run_tool",
]
