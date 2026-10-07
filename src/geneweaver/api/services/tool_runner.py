"""How a tool gets executed -- the seam between the API and the execution backend.

Tools run out of process through **AsyncTask** (`bitbucket.org/jacksonlaboratory/asynctask`),
a Temporal-backed service that loads them as the `GeneWeaverTools` plugin. That path is
`services/asynctask.py`, chosen per request in `services/tools.py`: it acts as the signed-in
user (every run requires one), and it is off wherever `ASYNCTASK_API_URL` is unset.

This module is the **in-process** backend for environments without AsyncTask. In-process execution is only
viable because the seven tools it serves are pure Python and fast; MSET and PhenomeMap shell
out to binaries the API image does not carry, and run only on AsyncTask.
"""

from typing import Protocol

from geneweaver.tools.framework.abstract import AbstractTool
from geneweaver.tools.framework.schema import ToolInput, ToolOutput


class ToolRunner(Protocol):
    """Executes a tool against its input and returns the result."""

    def run(self, tool: AbstractTool, tool_input: ToolInput) -> ToolOutput:
        """Run the tool and return its output."""
        ...


class InProcessToolRunner:
    """Run the tool in the API process, synchronously.

    Suitable only for tools that are fast and need no native binary. The request blocks
    for the duration of the run, so this holds a worker thread.
    """

    def run(self, tool: AbstractTool, tool_input: ToolInput) -> ToolOutput:
        """Run the tool inline and return its output."""
        return tool.run(tool_input)
