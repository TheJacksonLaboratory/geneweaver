"""What a tool run was asked to do, kept with the run in AsyncTask (G3-801).

v3 keeps no run table (roadmap §4 guardrail 1): AsyncTask stores the run, its owner and its
input. But the input it stores is the *resolved* envelope -- gene lists, a signed identity --
not the request that produced it, and a run carries no tool name of its own. Three things
need the request:

- **listing** a user's runs by tool and gene sets;
- **rerunning** one: it goes back through the access gate and the input resolvers, and ABBA
  and Similar gene sets are signed again, since their identity expires (6 h);
- **reading** a result, which re-checks that the caller may still read the run's gene sets
  (G3-736): a result is the gene sets' contents.

So the API writes the request, as JSON, into the free-text ``description`` AsyncTask keeps on
every input and returns from ``GET /inputs``. A run whose description is not one of these
(submitted before G3-801, or by another client) has no record; it can be read only when its
gene sets can be found in its envelope, and cannot be rerun.
"""

import json
from dataclasses import dataclass, field
from typing import Any

#: Marks a description as a run record, and its format. Bump it for an incompatible change
#: and keep reading the old one, since stored runs outlive deployments.
RECORD_KEY = "geneweaver_tool_run"
RECORD_VERSION = 1


@dataclass(frozen=True)
class RunRecord:
    """A run's tool, the gene sets it reads, and the request to submit it again.

    :param tool: The endpoint's tool name: a registry name, ``abba`` or ``similar_genesets``.
    :param geneset_ids: Every gene set the run reads, for the access check on read.
    :param request: What the tool's run endpoint takes: ``{geneset_ids, parameters}`` for a
        registered tool, the request body for ABBA and Similar gene sets.
    """

    tool: str
    geneset_ids: list[int]
    request: dict[str, Any] = field(default_factory=dict)

    def to_description(self) -> str:
        """The record as AsyncTask's input description."""
        return json.dumps(
            {
                RECORD_KEY: RECORD_VERSION,
                "tool": self.tool,
                "geneset_ids": self.geneset_ids,
                "request": self.request,
            },
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        )

    @classmethod
    def from_description(cls, description: object) -> "RunRecord | None":
        """Read a record back, or None for a description that is not one.

        Anything malformed is None rather than an error: a description is free text, and
        one this code did not write must not make the user's run list fail.
        """
        if not isinstance(description, str) or RECORD_KEY not in description:
            return None
        try:
            data = json.loads(description)
        except ValueError:
            return None
        if not isinstance(data, dict) or data.get(RECORD_KEY) != RECORD_VERSION:
            return None
        tool, geneset_ids, request = data.get("tool"), data.get("geneset_ids"), data.get("request")
        if (
            not isinstance(tool, str)
            or not isinstance(geneset_ids, list)
            or not all(isinstance(i, int) and not isinstance(i, bool) for i in geneset_ids)
            or not isinstance(request, dict)
        ):
            return None
        return cls(tool=tool, geneset_ids=geneset_ids, request=request)
