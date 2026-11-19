"""A run's result as a file (G3-801).

The results are real tool outputs, run in-process and passed through JSON as AsyncTask
stores them -- integer keys become strings, tuples lists -- so a table that reads a shape
the tool does not produce fails here rather than in a user's download.
"""

import csv
import io
import json

import pytest
from geneweaver.tools.boolean_algebra import BooleanAlgebra, BooleanAlgebraInput
from geneweaver.tools.combine import Combine, CombineInput
from geneweaver.tools.dbscan import DBSCAN, DBSCANInput
from geneweaver.tools.jaccard_clustering import JaccardClustering, JaccardClusteringInput
from geneweaver.tools.jaccard_similarity import JaccardSimilarity, JaccardSimilarityInput
from geneweaver.tools.upset import UpSet, UpSetInput

from geneweaver.api.services import tool_downloads as downloads
from geneweaver.api.services.tool_inputs import jaccard_pair_counts, similarity_matrix

MEMBERSHIPS = {"5": ["Drd2", "Th", "Comt"], "6": ["Drd2", "Th"], "7": ["Comt"]}


def _stored(tool, tool_input) -> dict:
    """The tool's output as AsyncTask stores it: through JSON."""
    return json.loads(json.dumps(tool.run(tool_input).model_dump(mode="json")))


def _rows(download: downloads.Download, delimiter: str = ",") -> list[list[str]]:
    return list(csv.reader(io.StringIO(download.content.decode()), delimiter=delimiter))


def test_json_is_the_result_itself_for_any_tool() -> None:
    """Every tool, even one with no table."""
    result = {"tree": None, "geneset_ids": []}

    download = downloads.render("jaccard_clustering", result, "json", None, 7)

    assert json.loads(download.content) == result
    assert (download.media_type, download.filename) == (
        "application/json",
        "jaccard_clustering-run7.json",
    )


def test_upset_intersections_as_csv() -> None:
    """Each combination of gene sets and its exclusive size."""
    result = _stored(
        UpSet(), UpSetInput(geneset_ids=["5", "6", "7"], gene_memberships=MEMBERSHIPS)
    )

    rows = _rows(downloads.render("upset", result, "csv", None, 1))

    assert rows[0] == ["genesets", "size"]
    assert ["5;6", "2"] in rows


def test_jaccard_pairs_name_gene_sets_not_positions() -> None:
    """The tool's i and j index the run's gene sets; the file names them."""
    ids = [5, 6, 7]
    tool_input = JaccardSimilarityInput(
        geneset_ids=[str(i) for i in ids], pairs=jaccard_pair_counts(MEMBERSHIPS, ids)
    )
    result = _stored(JaccardSimilarity(), tool_input)

    rows = _rows(downloads.render("jaccard_similarity", result, "tsv", None, 1), "\t")

    assert rows[0][:3] == ["geneset_a", "geneset_b", "jaccard"]
    pair = next(row for row in rows[1:] if row[:2] == ["5", "6"])
    assert float(pair[2]) == pytest.approx(2 / 3)


def test_combine_matrix_as_legacys_odemat() -> None:
    """Counts and GS ids, then labels, then one 0/1 row per gene, as legacy wrote it."""
    rows = [[5, 1, "Drd2"], [5, 2, "Th"], [6, 1, "Drd2"]]
    tool_input = CombineInput(
        geneset_ids=[5, 6],
        include_homology=False,
        membership_rows=rows,
        label_rows=[[5, "Dopamine set", "DA"], [6, "Other", "OT"]],
    )
    result = _stored(Combine(), tool_input)

    lines = downloads.render("combine", result, "odemat", None, 1).content.decode().splitlines()

    assert lines[0] == "2\t2\tGS5\tGS6"
    assert lines[1] == "\tDA\tOT"
    assert sorted(lines[2:]) == ["1\tDrd2\t1\t1", "2\tTh\t1\t0"]


def test_combine_matrix_as_csv_too() -> None:
    """The same matrix with a header row."""
    tool_input = CombineInput(
        geneset_ids=[5], include_homology=False, membership_rows=[[5, 1, "Drd2"]]
    )

    rows = _rows(downloads.render("combine", _stored(Combine(), tool_input), "csv", None, 1))

    assert rows == [["gene_id", "gene", "GS5"], ["1", "Drd2", "1"]]


def test_boolean_algebra_lists_the_relations_answer() -> None:
    """Intersection: only genes in at least N gene sets, with their distinct gene sets."""
    homologs = [
        [None, 1, "Drd2", 1, 5, "A"],
        [None, 1, "Drd2", 1, 6, "B"],
        [None, 2, "Th", 1, 5, "A"],
    ]
    tool_input = BooleanAlgebraInput(
        relation="intersection",
        at_least=2,
        geneset_ids=[5, 6],
        species_ids=[1],
        homolog_data=homologs,
    )
    result = _stored(BooleanAlgebra(), tool_input)

    rows = _rows(downloads.render("boolean_algebra", result, "csv", None, 1))

    assert rows[0] == ["key", "genes", "species_ids", "geneset_ids"]
    assert [row[1:] for row in rows[1:]] == [["Drd2", "1", "5;6"]]


def test_dbscan_clusters_one_gene_a_row() -> None:
    """Numbered clusters."""
    tool_input = DBSCANInput(
        gene_symbols=MEMBERSHIPS, epsilon=1, min_points=1, geneset_ids=["5", "6", "7"]
    )
    result = _stored(DBSCAN(), tool_input)

    rows = _rows(downloads.render("dbscan", result, "csv", None, 1))

    assert rows[0] == ["cluster", "gene"]
    assert {row[1] for row in rows[1:]} <= {"Drd2", "Th", "Comt"}


def test_a_clustering_tree_as_newick() -> None:
    """Leaves are gene sets; the tree ends in a semicolon."""
    ids = ["5", "6", "7"]
    tool_input = JaccardClusteringInput(
        geneset_ids=ids, method="average", similarity=similarity_matrix(MEMBERSHIPS, [5, 6, 7])
    )
    result = _stored(JaccardClustering(), tool_input)

    text = downloads.render("jaccard_clustering", result, "newick", None, 1).content.decode()

    assert text.endswith(";\n")
    assert all(f"GS{gs}" in text for gs in ids)
    assert text.count("(") == text.count(")") == 2


def test_abba_offers_both_its_tables() -> None:
    """Gene sets by default, genes when asked."""
    result = {
        "genesets": [{"gs_id": 5, "name": "A", "matches": 2}],
        "genes": [
            {"symbol": "Th", "species": "Mus musculus", "occurrences": 3, "symbols": ["Th", "TH"]}
        ],
    }

    by_default = _rows(downloads.render("abba", result, "csv", None, 1))
    genes = downloads.render("abba", result, "csv", "genes", 1)

    assert by_default[0][0] == "gs_id"
    assert _rows(genes)[1] == ["Th", "Mus musculus", "3", "Th;TH"]
    assert genes.filename == "abba-run1-genes.csv"


def test_similar_genesets_keeps_legacys_export_columns() -> None:
    """gs_id, name, abbreviation, count and jaccard, as legacy's "Export GeneSets"."""
    result = {
        "genesets": [
            {
                "gs_id": 5,
                "name": "A",
                "abbreviation": "a",
                "genes": 9,
                "shared": 3,
                "jaccard": 0.25,
            }
        ]
    }

    rows = _rows(downloads.render("similar_genesets", result, "csv", None, 1))

    assert rows[0][:6] == ["gs_id", "name", "abbreviation", "genes", "shared", "jaccard"]
    assert rows[1][:6] == ["5", "A", "a", "9", "3", "0.25"]


@pytest.mark.parametrize(
    ("tool", "fmt", "table"),
    [
        ("jaccard_clustering", "csv", None),
        ("upset", "odemat", None),
        ("upset", "newick", None),
        (None, "csv", None),
        ("abba", "csv", "nodes"),
    ],
)
def test_a_format_or_table_the_tool_lacks_is_refused(tool, fmt, table) -> None:
    """A 422 naming what the tool does offer."""
    with pytest.raises(downloads.DownloadError):
        downloads.render(tool, {"genesets": [], "genes": []}, fmt, table, 1)


def test_every_tool_downloads_as_json() -> None:
    """And a tool with tables offers csv and tsv."""
    assert downloads.formats_for(None) == ["json"]
    assert downloads.formats_for("combine") == ["json", "csv", "tsv", "odemat"]
    assert downloads.formats_for("jaccard_clustering") == ["json", "newick"]


def test_intersect_is_read_as_intersection() -> None:
    """The API's other spelling: the tool titles it "Intersect", not "Intersection"."""
    homologs = [
        [None, 1, "Drd2", 1, 5, "A"],
        [None, 1, "Drd2", 1, 6, "B"],
        [None, 2, "Th", 1, 5, "A"],
    ]
    tool_input = BooleanAlgebraInput(
        relation="intersect",
        at_least=2,
        geneset_ids=[5, 6],
        species_ids=[1],
        homolog_data=homologs,
    )
    result = _stored(BooleanAlgebra(), tool_input)

    rows = _rows(downloads.render("boolean_algebra", result, "csv", None, 1))

    assert [row[1] for row in rows[1:]] == ["Drd2"]
