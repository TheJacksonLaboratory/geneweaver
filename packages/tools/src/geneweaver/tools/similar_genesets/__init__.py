"""Similar gene sets, legacy's "Find Similar GeneSets" (``/viewSimilarGenesets``).

The gene sets most like one gene set, by Jaccard over their genes -- homologs counted as one
gene -- with the run's threshold choice. Like ABBA it is a database search, not a
computation over input it is handed, so it is not in the `geneweaver.tools` registry: it
runs on AsyncTask through the same `GeneWeaverToolWorkflow`, which the activity recognises
by name (`temporal.activities.DATABASE_TOOLS`).

Read-only: legacy wrote every result into ``geneset_jaccard`` on every view; this never
writes. That table is legacy's cache while legacy runs; the v3 cache is planned for when
legacy is turned off (docs/tools/TOOLS_MIGRATION.md, "Similar gene sets: the cache").

Importing this package needs only pydantic; `search` needs the `db` extra.
"""

from geneweaver.tools.similar_genesets.schema import (
    SimilarGeneset,
    SimilarGenesetsInput,
    SimilarGenesetsOutput,
)

#: The name a request envelope gives, `{"tool": "similar_genesets", ...}`.
TOOL_NAME = "similar_genesets"

__all__ = ["TOOL_NAME", "SimilarGeneset", "SimilarGenesetsInput", "SimilarGenesetsOutput"]
