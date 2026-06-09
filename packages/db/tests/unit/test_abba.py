"""Unit tests for the ABBA association db functions."""

from unittest.mock import MagicMock

from geneweaver.db.abba import ABBAResult, abba
from geneweaver.db.query import abba as q
from psycopg.sql import Composed, Identifier


def _render(composable) -> str:
    """Render a SQL/Composed to text without a DB connection (quotes identifiers itself)."""
    if isinstance(composable, Identifier):
        return '"' + '"."'.join(composable._obj) + '"'
    if isinstance(composable, Composed):
        return "".join(_render(part) for part in composable)
    return composable.as_string(None)


def _sql(builder_result) -> str:
    """Render a (SQL, params) builder result's SQL to a string for assertions."""
    return " ".join(_render(builder_result[0]).split())


# --------------------------------------------------------------------- query builders


def test_list_values_bind_as_parameters_not_interpolated() -> None:
    """Lists bind via = ANY(%(...)s) (no string-joined IN clause / injection risk)."""
    sql, params = q.create_input_genes_table("t", ["BRCA1", "Trp53"], [1, 2])
    rendered = _sql((sql, params))
    assert "= ANY(%(genes)s)" in rendered
    assert "sp_id = ANY(%(species)s)" in rendered
    # genes are lower-cased; species/gdb bind as params
    assert params["genes"] == ["brca1", "trp53"]
    assert params["species"] == [1, 2]
    assert params["gdb_id"] == q.GENE_SYMBOL_GDB_ID


def test_temp_table_name_is_quoted_identifier() -> None:
    """Temp-table names render as quoted identifiers, not raw text."""
    assert 'CREATE TEMP TABLE "abba_x"' in _sql(q.create_input_genes_table("abba_x", [], [1]))


def test_genes_of_interest_no_homology_creates_table() -> None:
    """The no-homology branch creates the interest table (legacy bug fixed)."""
    sql, params = q.create_genes_of_interest_table("i", "in", [1], include_homology=False)
    rendered = _sql((sql, params))
    assert rendered.startswith('CREATE TEMP TABLE "i" AS SELECT * FROM "in"')
    assert params == {}


def test_genes_of_interest_with_homology_unions_input() -> None:
    """The homology branch expands via homology and unions the original input genes."""
    rendered = _sql(q.create_genes_of_interest_table("i", "in", [1, 2], include_homology=True))
    assert "extsrc.homology" in rendered
    assert 'UNION DISTINCT (SELECT * FROM "in")' in rendered
    assert "sp_id = ANY(%(species)s)" in rendered


def test_result_genes_auto_min_uses_least_expression() -> None:
    """min_genes=None gates by least(count(distinct interest genes), 1)."""
    sql, params = q.create_result_genes_table("r", "m", "i", [1, 2], [1], None)
    rendered = _sql((sql, params))
    assert "least((SELECT count(DISTINCT ode_ref_id) FROM" in rendered
    assert "min_genes" not in params


def test_result_genes_explicit_min_binds_param() -> None:
    """An explicit min_genes binds as a parameter."""
    sql, params = q.create_result_genes_table("r", "m", "i", [1], [1], 3)
    assert ">= %(min_genes)s" in _sql((sql, params))
    assert params["min_genes"] == 3


def test_count_genesets_by_tier_excludes_deprecated() -> None:
    """Per-tier counts exclude deprecated gene sets via a parameterised pattern."""
    sql, params = q.count_genesets_by_tier(42)
    assert "gs_status NOT LIKE %(deprecated)s" in _sql((sql, params))
    assert params == {"ode_gene_id": 42, "deprecated": "de%"}


# --------------------------------------------------------------------- orchestration


def _orchestration_cursor() -> MagicMock:
    """A cursor mock that returns canned rows for one result gene (ode_gene_id 42)."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        [100],  # count_available_genes
        [2000],  # count_available_genesets
        ["SYM1"],  # preferred ref id for gene 42
    ]
    cursor.fetchall.side_effect = [
        [(42, "Sym1", "mouse")],  # genes_of_interest
        [("mouse",)],  # input_species
        [(10, "GS A", 3, 1, 1)],  # matching geneset_results
        [(42, "ref42", "mouse", 1, 5)],  # gene_results (one gene)
        [(5,)],  # max_occurrences
        [("ref42",), ("ref42b",)],  # gene ref ids for 42 (one column, two rows)
        [(7, 1), (2, 2)],  # genesets by tier -> {1:7, 2:2}
        [(3, 1), (1, 4)],  # genesets by species -> {1:3, 4:1}
    ]
    return cursor


def test_abba_orchestration_collects_results() -> None:
    """abba() runs the pipeline and assembles the structured result."""
    cursor = _orchestration_cursor()

    result = abba(cursor, ["Brca1"], species_ids=[1], tiers=[1, 2, 3])

    assert isinstance(result, ABBAResult)
    assert result.available_genes == 100
    assert result.available_genesets == 2000
    assert result.gene_results == [(42, "ref42", "mouse", 1, 5)]
    assert result.ode_mapping[42] == ["ref42", "ref42b"]
    assert result.preferred_mapping[42] == "SYM1"
    assert result.tier_counts[42] == {1: 7, 2: 2}
    assert result.species_counts[42] == {1: 3, 4: 1}
    assert result.max_occurrences == [(5,)]


def test_abba_creates_unique_temp_tables() -> None:
    """Each run drops + creates four uniquely-named session temp tables."""
    cursor = _orchestration_cursor()
    abba(cursor, ["Brca1"], species_ids=[1], tiers=[1])

    creates = [
        _render(c.args[0])
        for c in cursor.execute.call_args_list
        if "CREATE TEMP TABLE" in _render(c.args[0])
    ]
    assert len(creates) == 4
    # names are suffixed for concurrency safety
    assert any("abba_input_genes_" in s for s in creates)
    assert any("abba_result_genes_" in s for s in creates)


def test_abba_merges_genes_from_input_genesets() -> None:
    """Gene sets contribute their member ref ids to the input gene list."""
    cursor = _orchestration_cursor()
    # First fetchall must serve the ref-ids-for-genesets query, so prepend it.
    cursor.fetchall.side_effect = [
        [("Pten",), ("Egfr",)],  # ref_ids_for_genesets
        *cursor.fetchall.side_effect,
    ]
    abba(cursor, ["Brca1"], geneset_ids=[55], species_ids=[1], tiers=[1])

    # The input-genes CREATE binds the merged, lower-cased gene set.
    create_call = next(
        c
        for c in cursor.execute.call_args_list
        if "abba_input_genes_" in _render(c.args[0]) and "CREATE TEMP TABLE" in _render(c.args[0])
    )
    assert set(create_call.args[1]["genes"]) == {"brca1", "pten", "egfr"}
