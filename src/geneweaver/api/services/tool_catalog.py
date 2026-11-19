"""What each analysis tool is, and the options its form offers, from the database (G3-801).

Legacy built its tool forms from `odestatic.tool` (name, description, order, whether it is
active) and `odestatic.tool_param` (each option's description, default, choices and widget),
under its own names: ``DBSCAN_minPts``, ``"Included"``/``"Excluded"``. The v3 tools take
other names and types -- ``min_points``, ``true``/``false`` -- so the rows are served here
with the v3 parameter each one sets and its values in v3's types, and the analysis page can
render a form from them rather than keeping its own copy (`tool-options.ts`).

Visible legacy options v3 cannot honour are listed apart, with why, rather than dropped
silently; options legacy itself hid (``tp_visible = false``) are left out.
"""

import json
from dataclasses import dataclass
from typing import Any

from geneweaver.db import tool as db_tool
from geneweaver.tools.thresholds import ThresholdOptions
from psycopg import Cursor

from geneweaver.api.services.tools import UnknownToolError, tool_availability

#: v3 tool -> legacy classname. UpSet and Similar gene sets have no `odestatic.tool` row.
LEGACY_CLASSNAMES: dict[str, str | None] = {
    "abba": "ABBA",
    "boolean_algebra": "BooleanAlgebra",
    "combine": "Combine",
    "dbscan": "DBSCAN",
    "geneset_graph": "GeneSetViewer",
    "hypergeometric": "HyperGeometric",
    "jaccard_clustering": "JaccardClustering",
    "jaccard_similarity": "JaccardSimilarity",
    "mset": "MSET",
    "phenome_map": "PhenomeMap",
    "triclique": "TricliqueViewer",
    "upset": None,
    "similar_genesets": None,
}

#: Names and descriptions for tools with no `odestatic.tool` row.
UNLISTED_TOOLS: dict[str, tuple[str, str]] = {
    "upset": ("UpSet", "Count the genes in each combination of the gene sets (an UpSet plot)."),
    "similar_genesets": (
        "Similar GeneSets",
        "Find the gene sets most like one gene set, by Jaccard similarity of their genes.",
    ),
}


@dataclass(frozen=True)
class ParameterSpec:
    """The v3 parameter a legacy option sets, and how its values convert.

    :param kind: ``flag`` (Included/Enabled/On/True -> true), ``integer``, ``number``,
        ``lower`` (a lowercased choice), or ``degree`` (an integer or ``"auto"``).
    """

    key: str
    kind: str


def _homology(classname: str) -> tuple[str, ParameterSpec]:
    return f"{classname}_Homology", ParameterSpec("include_homology", "flag")


#: Legacy ``tp_name`` -> the v3 parameter it sets.
PARAMETERS: dict[str, ParameterSpec] = dict(
    [
        *(
            _homology(c)
            for c in (
                "Combine",
                "DBSCAN",
                "GeneSetViewer",
                "HyperGeometric",
                "JaccardClustering",
                "JaccardSimilarity",
                "PhenomeMap",
                "TricliqueViewer",
            )
        ),
        ("BooleanAlgebra_Relation", ParameterSpec("relation", "lower")),
        ("DBSCAN_epsilon", ParameterSpec("epsilon", "integer")),
        ("DBSCAN_minPts", ParameterSpec("min_points", "integer")),
        ("GeneSetViewer_MinDegree", ParameterSpec("min_degree", "degree")),
        ("GeneSetViewer_SupressDisconnected", ParameterSpec("suppress_disconnected", "flag")),
        ("HyperGeometric_PairwiseDeletion", ParameterSpec("pairwise_deletion", "flag")),
        ("JaccardClustering_Method", ParameterSpec("method", "lower")),
        ("JaccardSimilarity_PairwiseDeletion", ParameterSpec("pairwise_deletion", "flag")),
        ("JaccardSimilarity_p-Value", ParameterSpec("p_value_threshold", "number")),
        ("MSET_NumberofTrials", ParameterSpec("number_of_samples", "integer")),
        ("PhenomeMap_DisableBootstrap", ParameterSpec("disable_bootstrap", "flag")),
        ("PhenomeMap_MaxLevel", ParameterSpec("max_level", "integer")),
        ("PhenomeMap_MinGenes", ParameterSpec("min_genes", "integer")),
        ("PhenomeMap_UseFDR", ParameterSpec("use_fdr", "flag")),
        ("PhenomeMap_p-Value", ParameterSpec("p_value_threshold", "number")),
    ]
)

#: Visible legacy options v3 does not offer, and why.
UNSUPPORTED: dict[str, str] = {
    "PhenomeMap_MaxInNode": "How many symbols a node shows is the page's choice, not the tool's.",
    "PhenomeMap_HideUnEmphasized": "Emphasis genes are not supported in v3 yet.",
    "PhenomeMap_Permutations": "The permutation test (an add-on in legacy) is not ported.",
    "PhenomeMap_PermutationTimeLimit": "The permutation test (an add-on in legacy) is not ported.",
    "TricliqueViewer_Methods": "v3's Triclique uses exact gene overlap only.",
}

#: Options v3 adds that legacy's table has no row for.
V3_PARAMETERS: dict[str, list[dict[str, Any]]] = {
    "upset": [
        {
            "key": "include_homology",
            "label": "Homology",
            "description": "Collapse homologous genes across species.",
            "type": "boolean",
            "widget": "radio",
            "default": False,
            "options": [True, False],
            "legacy_name": None,
        },
        {
            "key": "include_zeros",
            "label": "Include empty combinations",
            "description": "Also list the combinations no gene belongs to.",
            "type": "boolean",
            "widget": "checkbox",
            "default": False,
            "options": [],
            "legacy_name": None,
        },
    ],
    "boolean_algebra": [
        {
            "key": "at_least",
            "label": "In at least N gene sets",
            "description": "For an intersection: the genes found in at least this many gene sets.",
            "type": "integer",
            "widget": "number",
            "default": 2,
            "options": [],
            "legacy_name": None,
        }
    ],
}

_TRUE = {"true", "1", "yes", "on", "included", "enabled"}
_FALSE = {"false", "0", "no", "off", "excluded", "disabled"}
_TYPES = {"flag": "boolean", "integer": "integer", "number": "number", "lower": "string"}


def convert(kind: str, value: Any) -> Any:
    """A legacy option value in v3's type; returned unchanged if it does not convert."""
    try:
        if kind == "flag":
            text = str(value).strip().lower()
            return True if text in _TRUE else False if text in _FALSE else value
        if kind == "integer":
            return int(value)
        if kind == "number":
            return float(value)
        if kind == "lower":
            return str(value).lower()
        if kind == "degree":
            return "auto" if str(value).strip().lower() == "auto" else int(value)
    except (TypeError, ValueError):
        return value
    return value


def _options(raw: object) -> list[Any]:
    """``tp_options``: a JSON list as text; anything else is no choices."""
    if not isinstance(raw, str):
        return []
    try:
        options = json.loads(raw)
    except ValueError:
        return []
    return options if isinstance(options, list) else []


def _widget(seltype: object, kind: str, options: list[Any]) -> str:
    """How legacy drew it, corrected: its table spells checkbox "chechbox" once."""
    if kind in ("integer", "number", "degree") and not options:
        return "number"
    text = str(seltype or "select").lower()
    return "checkbox" if text in ("checkbox", "chechbox") else text


def parameter(row: dict[str, Any]) -> dict[str, Any] | None:
    """One `tool_param` row as a v3 form field, or None if v3 does not offer it."""
    spec = PARAMETERS.get(row["tp_name"])
    if spec is None:
        return None
    options = [convert(spec.kind, option) for option in _options(row.get("tp_options"))]
    if spec.kind in ("integer", "number", "degree") and len(options) <= 1:
        # A one-entry list is legacy's placeholder (DBSCAN's ["1"]), not a choice.
        options = []
    default = convert(spec.kind, row.get("tp_default"))
    if options and default not in options:
        if spec.kind in ("integer", "number") and isinstance(default, int | float):
            # A real default legacy's list leaves out (Jaccard's p-value 1.0): offer it too.
            options = [default, *options]
        else:
            # Not a value at all (BooleanAlgebra's default is "False"): legacy showed the first.
            default = options[0]
    label = row["tp_name"].split("_", 1)[-1]
    return {
        "key": spec.key,
        "label": label,
        "description": row.get("tp_description"),
        "type": _TYPES.get(spec.kind, "integer"),
        "widget": _widget(row.get("tp_seltype"), spec.kind, options),
        "default": default,
        "options": options,
        "legacy_name": row["tp_name"],
    }


def _tool_row(rows: list[dict[str, Any]], classname: str | None) -> dict[str, Any] | None:
    return next((row for row in rows if row["tool_classname"] == classname), None)


#: Database searches with endpoints of their own, not registered tools: always runnable.
#: Similar gene sets is described but not listed -- it runs from a gene set's page on one
#: gene set, and the Analyze page offers every listed tool for a gene set selection.
_SEARCHES = {"abba": True, "similar_genesets": False}


def _availability(listed_only: bool = False) -> dict[str, dict[str, Any]]:
    tools = tool_availability()
    for name, listed in _SEARCHES.items():
        if listed or not listed_only:
            tools[name] = {"available": True, "reason": None, "caveat": None}
    return tools


def _summary(name: str, state: dict[str, Any], row: dict[str, Any] | None) -> dict[str, Any]:
    label, description = UNLISTED_TOOLS.get(name, (name, None))
    return {
        **state,
        "name": name,
        "label": row["tool_name"] if row else label,
        "description": row["tool_description"] if row else description,
        "legacy_classname": LEGACY_CLASSNAMES.get(name),
        "active_in_legacy": (str(row["tool_active"]) == "1") if row else None,
        "sort": row["tool_sort"] if row else None,
    }


def catalogue(cursor: Cursor) -> dict[str, dict[str, Any]]:
    """Every tool the API runs, with its availability and its `odestatic.tool` entry."""
    rows = db_tool.get_tools(cursor)
    return {
        name: _summary(name, state, _tool_row(rows, LEGACY_CLASSNAMES.get(name)))
        for name, state in _availability(listed_only=True).items()
    }


def describe(cursor: Cursor, name: str) -> dict[str, Any]:
    """One tool, with the form fields it takes.

    ``parameters`` are its options as v3 takes them; ``unsupported_legacy_parameters`` the
    legacy options it does not offer, with why; ``thresholds`` the JSON Schema of the run
    threshold options every tool accepts in ``parameters``.

    :raises UnknownToolError: For a name the API does not run.
    """
    state = _availability().get(name)
    if state is None:
        raise UnknownToolError(f"No tool registered as {name!r}.")
    classname = LEGACY_CLASSNAMES.get(name)
    row = _tool_row(db_tool.get_tools(cursor), classname)
    params = db_tool.get_tool_params(cursor, classname) if classname else []
    visible = [p for p in params if p.get("tp_visible") is not False]
    return {
        **_summary(name, state, row),
        "parameters": [field for p in visible if (field := parameter(p))]
        + V3_PARAMETERS.get(name, []),
        "unsupported_legacy_parameters": [
            {
                "legacy_name": p["tp_name"],
                "description": p.get("tp_description"),
                "reason": UNSUPPORTED[p["tp_name"]],
            }
            for p in visible
            if p["tp_name"] in UNSUPPORTED
        ],
        "thresholds": ThresholdOptions.model_json_schema(),
    }
