"""The worker side of the GeneWeaver tools on AsyncTask: the activity that runs a tool.

The workflow, the queue names and the request checks are `geneweaver-tools-plugin`
(`geneweaver.tools_plugin`), which is all AsyncTask installs. This package is what
GeneWeaver's own two workers run: the activity, the database look-ups that expand a request,
and the worker process. It reads the names it shares with the workflow from the plugin's
`contract` module rather than restating them.

Requires the ``temporal`` extra (``geneweaver-tools[temporal]``), which brings the plugin and
``temporalio``. Callers that only need the compute classes and their schemas -- the
GeneWeaver API, for one -- never import it.
"""

from .activities import available_tools, load_tool, run_tool

#: What the workers register. AsyncTask does not: the plugin declares no activities entry
#: point, and the workflow schedules this activity by name onto the workers' queues.
ACTIVITIES = [run_tool]

__all__ = [
    "ACTIVITIES",
    "available_tools",
    "load_tool",
    "run_tool",
]
