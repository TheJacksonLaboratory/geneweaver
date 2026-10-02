"""How a tool gets executed -- the seam between the API and the execution backend.

Tools run in production through **AsyncTask** (`bitbucket.org/jacksonlaboratory/asynctask`),
a Temporal-backed service that loads them as `jax.ats.plugins` entry points. Reaching that
needs two changes outside this repository: publishing `geneweaver-tools` to the private
`gcp-dev` index, and adding it to `asynctask`'s dependencies.

Until those land, tools run **in-process and synchronously** so the `/next` UI can exercise
the whole chain against dev. This module is the one place that knows the difference.
Swapping to AsyncTask means adding an `AsyncTaskToolRunner` here and choosing it in
`dependencies.py` -- the service layer, the endpoints and the UI do not change.

In-process execution is only viable because the first tools exposed are the cheap ones.
UpSet is pure Python over set membership. It is **not** a general answer: MSET and
PhenomeMap shell out to binaries, and the roadmap's A4 notes that tool runs take
seconds to minutes, which is why AsyncTask exists.
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
