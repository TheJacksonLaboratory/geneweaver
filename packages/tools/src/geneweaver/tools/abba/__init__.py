"""ABBA, legacy's "Anchored Biclique of Biomolecular Associations" gene-centred search.

Not registered in the `geneweaver.tools` entry-point group: the registered tools are pure
computations over the input they are handed, and ABBA is a database search. It runs on
AsyncTask through the same `GeneWeaverToolWorkflow`, which the activity recognises by name
(`temporal.activities.DATABASE_TOOLS`).

Importing this package needs only pydantic; `search` needs the `db` extra.
"""

from geneweaver.tools.abba.schema import ABBAInput, ABBAOutput

#: The name a request envelope gives, `{"tool": "abba", ...}`.
TOOL_NAME = "abba"

__all__ = ["TOOL_NAME", "ABBAInput", "ABBAOutput"]
