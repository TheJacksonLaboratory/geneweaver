"""Tool forms from `odestatic.tool` and `tool_param` (G3-801).

The rows are dev's (2026-11-19), as read from the database, so the mapping is tested against
what legacy's table actually holds -- its placeholders and typos included.
"""

from unittest.mock import Mock, patch

import pytest

from geneweaver.api.services import tool_catalog as catalog
from geneweaver.api.services.tools import UnknownToolError

# (tool_classname, tp_name, tp_default, tp_options, tp_seltype, tp_visible)
DEV_PARAMS = [
    (
        "BooleanAlgebra",
        "BooleanAlgebra_Relation",
        "False",
        '["Union","Intersection","Except"]',
        "radio",
        True,
    ),
    ("Combine", "Combine_Homology", "Included", '["Included","Excluded"]', "select", True),
    ("DBSCAN", "DBSCAN_epsilon", "1", '["1"]', "select", True),
    ("DBSCAN", "DBSCAN_Homology", "Included", '["Included","Excluded"]', "select", True),
    ("DBSCAN", "DBSCAN_minPts", "1", '["1"]', "select", True),
    (
        "GeneSetViewer",
        "GeneSetViewer_Homology",
        "Included",
        '["Included","Excluded"]',
        "select",
        True,
    ),
    ("GeneSetViewer", "GeneSetViewer_MinDegree", "1", '["1"]', "select", True),
    ("GeneSetViewer", "GeneSetViewer_SupressDisconnected", "On", '["Off", "On"]', "select", True),
    (
        "HyperGeometric",
        "HyperGeometric_Homology",
        "Included",
        '["Included","Excluded"]',
        "select",
        True,
    ),
    (
        "HyperGeometric",
        "HyperGeometric_PairwiseDeletion",
        "Disabled",
        '["Disabled","Enabled"]',
        "checkbox",
        True,
    ),
    (
        "JaccardClustering",
        "JaccardClustering_Homology",
        "Included",
        '["Included","Excluded"]',
        "select",
        True,
    ),
    (
        "JaccardClustering",
        "JaccardClustering_Method",
        "Ward",
        '["Ward","Single","Centroid","McQuitty","Average","Complete"]',
        "select",
        True,
    ),
    (
        "JaccardSimilarity",
        "JaccardSimilarity_Homology",
        "Included",
        '["Included","Excluded"]',
        "select",
        True,
    ),
    (
        "JaccardSimilarity",
        "JaccardSimilarity_PairwiseDeletion",
        "Disabled",
        '["Disabled","Enabled"]',
        "checkbox",
        True,
    ),
    (
        "JaccardSimilarity",
        "JaccardSimilarity_p-Value",
        "1.0",
        '["0.5","0.10","0.05","0.01","0"]',
        "select",
        True,
    ),
    ("MSET", "MSET_Background", "CTD", '["CTD","NIF"]', "select", False),
    ("MSET", "MSET_NumberofSamples", "100", '["100","1000","5000","10000"]', "select", False),
    ("MSET", "MSET_NumberofTrials", "5000", '["5000", "10000", "15000", "30000"]', "select", True),
    ("PhenomeMap", "PhenomeMap_DisableBootstrap", "False", '["False","True"]', "checkbox", True),
    ("PhenomeMap", "PhenomeMap_GenesInNode", "All", '["All", "Exclusive"]', "select", False),
    ("PhenomeMap", "PhenomeMap_HideUnEmphasized", "False", '["False","True"]', "checkbox", True),
    ("PhenomeMap", "PhenomeMap_Homology", "Included", '["Included","Excluded"]', "select", True),
    ("PhenomeMap", "PhenomeMap_MaxInNode", "4", "[4,8,12,16,20,24,28,32]", "select", True),
    ("PhenomeMap", "PhenomeMap_MaxLevel", "40", "[0,10,20,40,60,80,100]", "select", True),
    ("PhenomeMap", "PhenomeMap_MinGenes", "1", "[1,2,3,4,5,6,7,8,9,10,15,20,25]", "select", True),
    ("PhenomeMap", "PhenomeMap_MinOverlap", "0%", '["0%","5%"]', "select", False),
    ("PhenomeMap", "PhenomeMap_NodeCutoff", "Auto", '["Auto",1.0,0.1]', "select", False),
    (
        "PhenomeMap",
        "PhenomeMap_Permutations",
        "0",
        "[100000,50000,25000,5000,1000,500,100,0]",
        "select",
        True,
    ),
    ("PhenomeMap", "PhenomeMap_PermutationTimeLimit", "5", "[5,10,15,20]", "select", True),
    (
        "PhenomeMap",
        "PhenomeMap_p-Value",
        "1.0",
        '["1.0","0.5","0.10","0.05","0.01"]',
        "select",
        True,
    ),
    ("PhenomeMap", "PhenomeMap_UseFDR", "False", '["False","True"]', "checkbox", True),
    (
        "TricliqueViewer",
        "TricliqueViewer_Homology",
        "Included",
        '["Included", "Excluded"]',
        "select",
        True,
    ),
    (
        "TricliqueViewer",
        "TricliqueViewer_Methods",
        "Exact Gene Overlap",
        '["Exact Gene Overlap", "Jaccard Overlap"]',
        "chechbox",
        True,
    ),
]

DEV_TOOLS = [
    {
        "tool_classname": "DBSCAN",
        "tool_name": "DBSCAN",
        "tool_description": "Run the DBSCAN Tool",
        "tool_requirements": "matrix",
        "tool_active": "1",
        "tool_sort": 20,
    },
    {
        "tool_classname": "PhenomeMap",
        "tool_name": "HiSim Graph",
        "tool_description": "Biclique-based analysis",
        "tool_requirements": "matrix",
        "tool_active": "1",
        "tool_sort": 1,
    },
    {
        "tool_classname": "HyperGeometric",
        "tool_name": "Hypergeometric Tests",
        "tool_description": "Fisher's exact test",
        "tool_requirements": "pairwisedeletion_matrix",
        "tool_active": "0",
        "tool_sort": 4,
    },
]


def _row(classname, name, default, options, seltype, visible) -> dict:
    return {
        "tool_classname": classname,
        "tp_name": name,
        "tp_description": f"{name} help",
        "tp_default": default,
        "tp_options": options,
        "tp_seltype": seltype,
        "tp_visible": visible,
    }


ROWS = [_row(*row) for row in DEV_PARAMS]


def _field(name: str) -> dict:
    return catalog.parameter(next(row for row in ROWS if row["tp_name"] == name))


def test_every_visible_legacy_option_is_mapped_or_explained() -> None:
    """A new `tool_param` row cannot vanish from the form unnoticed."""
    for row in ROWS:
        if row["tp_visible"]:
            assert row["tp_name"] in catalog.PARAMETERS or row["tp_name"] in catalog.UNSUPPORTED


def test_homology_is_a_boolean_for_every_tool() -> None:
    """Legacy's "Included"/"Excluded" is v3's include_homology."""
    field = _field("DBSCAN_Homology")

    assert (field["key"], field["type"], field["default"]) == ("include_homology", "boolean", True)
    assert field["options"] == [True, False]
    assert field["legacy_name"] == "DBSCAN_Homology"


@pytest.mark.parametrize(
    ("name", "key", "default", "options"),
    [
        (
            "JaccardClustering_Method",
            "method",
            "ward",
            ["ward", "single", "centroid", "mcquitty", "average", "complete"],
        ),
        ("HyperGeometric_PairwiseDeletion", "pairwise_deletion", False, [False, True]),
        ("GeneSetViewer_SupressDisconnected", "suppress_disconnected", True, [False, True]),
        ("MSET_NumberofTrials", "number_of_samples", 5000, [5000, 10000, 15000, 30000]),
        ("PhenomeMap_MaxLevel", "max_level", 40, [0, 10, 20, 40, 60, 80, 100]),
        ("PhenomeMap_UseFDR", "use_fdr", False, [False, True]),
    ],
)
def test_options_take_v3s_names_and_types(name, key, default, options) -> None:
    """The names `POST /tools/{tool}` reads, the values it accepts."""
    field = _field(name)

    assert (field["key"], field["default"], field["options"]) == (key, default, options)


def test_a_default_missing_from_legacys_choices_is_offered_not_replaced() -> None:
    """Jaccard's p-value defaults to 1.0, which its legacy list leaves out."""
    field = _field("JaccardSimilarity_p-Value")

    assert field["default"] == 1.0
    assert field["options"] == [1.0, 0.5, 0.1, 0.05, 0.01, 0.0]


def test_a_default_that_is_no_choice_becomes_the_first() -> None:
    """BooleanAlgebra's stored default is "False", not a relation."""
    field = _field("BooleanAlgebra_Relation")

    assert (field["default"], field["options"]) == ("union", ["union", "intersection", "except"])


def test_a_one_entry_list_is_a_number_field_not_a_choice() -> None:
    """DBSCAN's ["1"] is legacy's placeholder."""
    field = _field("DBSCAN_minPts")

    assert (field["key"], field["widget"], field["options"], field["default"]) == (
        "min_points",
        "number",
        [],
        1,
    )
    assert _field("GeneSetViewer_MinDegree")["widget"] == "number"


def test_legacys_misspelt_checkbox_is_a_checkbox() -> None:
    """`tp_seltype` is "chechbox" for TricliqueViewer_Methods."""
    assert catalog._widget("chechbox", "lower", ["a"]) == "checkbox"


@pytest.mark.parametrize(
    ("value", "kind"), [("maybe", "flag"), ("x", "integer"), (None, "number")]
)
def test_a_value_that_does_not_convert_is_kept(value, kind) -> None:
    """A bad row shows as it is rather than breaking the tool's description."""
    assert catalog.convert(kind, value) == value


def _cursor_with(tools, params):
    def by_classname(cursor, classname=None):
        return [p for p in params if classname is None or p["tool_classname"] == classname]

    return (
        patch.object(catalog.db_tool, "get_tools", return_value=tools),
        patch.object(catalog.db_tool, "get_tool_params", side_effect=by_classname),
    )


def test_a_tool_is_described_with_its_fields_and_what_it_leaves_out() -> None:
    """PhenomeMap: hidden options gone, unported ones listed with why."""
    tools, params = _cursor_with(DEV_TOOLS, ROWS)
    with tools, params:
        described = catalog.describe(Mock(), "phenome_map")

    assert (described["label"], described["legacy_classname"], described["sort"]) == (
        "HiSim Graph",
        "PhenomeMap",
        1,
    )
    keys = [field["key"] for field in described["parameters"]]
    assert keys == [
        "disable_bootstrap",
        "include_homology",
        "max_level",
        "min_genes",
        "p_value_threshold",
        "use_fdr",
    ]
    unsupported = [p["legacy_name"] for p in described["unsupported_legacy_parameters"]]
    assert unsupported == [
        "PhenomeMap_HideUnEmphasized",
        "PhenomeMap_MaxInNode",
        "PhenomeMap_Permutations",
        "PhenomeMap_PermutationTimeLimit",
    ]
    assert "MinOverlap" not in str(described)
    assert described["thresholds"]["properties"]["threshold"]


def test_a_tool_without_a_legacy_row_still_has_its_v3_fields() -> None:
    """UpSet has no `odestatic.tool` row; its options are v3's own."""
    tools, params = _cursor_with(DEV_TOOLS, ROWS)
    with tools, params:
        described = catalog.describe(Mock(), "upset")

    assert (described["label"], described["legacy_classname"]) == ("UpSet", None)
    assert [f["key"] for f in described["parameters"]] == ["include_homology", "include_zeros"]


def test_an_unknown_tool_is_not_described() -> None:
    """404 at the endpoint."""
    tools, params = _cursor_with(DEV_TOOLS, ROWS)
    with tools, params, pytest.raises(UnknownToolError):
        catalog.describe(Mock(), "nope")


def test_the_catalogue_lists_every_tool_with_legacys_names() -> None:
    """Registered tools plus ABBA, named as legacy named them; Similar gene sets is not listed."""
    tools, params = _cursor_with(DEV_TOOLS, ROWS)
    with tools, params:
        listed = catalog.catalogue(Mock())
        similar = catalog.describe(Mock(), "similar_genesets")

    assert {"abba", "phenome_map", "upset"} <= set(listed)
    assert "similar_genesets" not in listed
    assert similar["label"] == "Similar GeneSets"
    assert listed["phenome_map"]["label"] == "HiSim Graph"
    assert listed["hypergeometric"]["active_in_legacy"] is False
    assert "available" in listed["dbscan"]
