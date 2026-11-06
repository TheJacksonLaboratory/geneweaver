"""Unit tests for the ABBA association db functions."""

from unittest.mock import MagicMock

import pytest
from geneweaver.db.abba import ABBAResult, abba
from geneweaver.db.query import abba as q
from geneweaver.db.query.membership import Thresholds
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
    assert rendered.startswith('CREATE TEMP TABLE "i" ON COMMIT DROP AS SELECT * FROM "in"')
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
    # Dropped when the caller's transaction ends, so a pooled connection does not carry
    # them into its next request.
    assert all("ON COMMIT DROP" in s for s in creates)
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


# ------------------------------------------------------------------ threshold choice

_MEMBERSHIP_QUERIES = {
    "seed": lambda t: q.ref_ids_for_genesets([1], t),
    "matching": lambda t: q.create_matching_genesets_table("m", "i", 0, t),
    "result": lambda t: q.create_result_genes_table("r", "m", "i", [1], [1], None, t),
    "tier_counts": lambda t: q.count_genesets_by_tier(42, t),
    "species_counts": lambda t: q.count_genesets_by_species(42, t),
}


@pytest.mark.parametrize("name", sorted(_MEMBERSHIP_QUERIES))
def test_every_membership_step_counts_every_gene_by_default(name) -> None:
    """The stored flag is not the rule any more: no choice, no filter."""
    rendered = _sql(_MEMBERSHIP_QUERIES[name](Thresholds()))
    assert "gsv_in_threshold" not in rendered


@pytest.mark.parametrize("name", sorted(_MEMBERSHIP_QUERIES))
def test_every_membership_step_applies_custom_cutoffs(name) -> None:
    """Each step reads the run's cutoffs, bound, against its own geneset alias."""
    sql, params = _MEMBERSHIP_QUERIES[name](Thresholds("custom", q_value=0.05))
    rendered = _sql((sql, params))
    assert params["t_q_value"] == 0.05
    assert "gs_threshold_type = 2 THEN" in rendered
    assert "<= %(t_q_value)s" in rendered


def test_the_pipeline_passes_the_choice_to_every_membership_step() -> None:
    """No step of the search falls back to another rule."""
    cursor = _orchestration_cursor()
    cursor.fetchall.side_effect = [[("Pten",)], *cursor.fetchall.side_effect]
    abba(
        cursor,
        ["Brca1"],
        geneset_ids=[55],
        species_ids=[1],
        tiers=[1],
        thresholds=Thresholds("custom", p_value=0.001),
    )
    bound = [
        c.args[1]["t_p_value"]
        for c in cursor.execute.call_args_list
        if len(c.args) > 1 and "t_p_value" in c.args[1]
    ]
    # seed, matching, result, and the tier and species counts for the one result gene
    assert bound == [0.001] * 5


# ------------------------------------------------------------- review findings 5, 6, 8


def test_matching_gene_sets_use_the_shared_readable_rule() -> None:
    """Search's rule (geneset_is_readable2), not legacy's "every group is the user's"."""
    rendered = _sql(q.create_matching_genesets_table("m", "i", 7))
    assert "@> string_to_array(gs_groups" not in rendered
    for case in (
        "gs.usr_id = %(user_id)s",
        "gs.gs_groups = '0'",
        "gs.cur_id < 5",
        "FROM production.project2geneset p2g",
        "u.usr_admin > 0",
    ):
        assert case in rendered


def test_seed_gene_sets_give_one_preferred_symbol_per_gene() -> None:
    """Not every identifier: other kinds match nothing, and synonyms pulled in other genes."""
    sql, params = q.ref_ids_for_genesets([5])
    rendered = _sql((sql, params))
    assert "g.gdb_id = %(gdb_id)s" in rendered
    assert "g.ode_pref" in rendered
    assert params["gdb_id"] == q.GENE_SYMBOL_GDB_ID


def test_a_search_with_time_left_bounds_each_statement_by_it() -> None:
    """Each statement's timeout is what is left of the budget, at most the per-statement cap."""
    import time

    cursor = _orchestration_cursor()
    abba(
        cursor,
        ["Brca1"],
        species_ids=[1],
        tiers=[1],
        deadline=time.monotonic() + 100,
        statement_timeout_seconds=30,
    )
    timeouts = [
        c.args[1][0]
        for c in cursor.execute.call_args_list
        if c.args and c.args[0] == "SELECT set_config('statement_timeout', %s, true)"
    ]
    assert timeouts
    assert all(value == "30000ms" for value in timeouts)  # 100 s left, capped at 30 s.


def test_a_search_out_of_time_stops_instead_of_running_on() -> None:
    """Past the deadline no further statement is sent."""
    import time

    from geneweaver.db.abba import ABBADeadlineExceeded

    cursor = _orchestration_cursor()
    with pytest.raises(ABBADeadlineExceeded):
        abba(cursor, ["Brca1"], species_ids=[1], tiers=[1], deadline=time.monotonic() - 1)
    cursor.execute.assert_not_called()


def test_a_statement_cancelled_at_the_deadline_is_reported_as_out_of_time() -> None:
    """Postgres cancelling the last statement reads as the budget, not a database error."""
    import time

    from geneweaver.db.abba import ABBADeadlineExceeded
    from psycopg import errors

    cursor = _orchestration_cursor()

    def execute(query, params=None):
        if "CREATE TEMP TABLE" in _render(query) if not isinstance(query, str) else False:
            raise errors.QueryCanceled("canceling statement due to statement timeout")

    cursor.execute.side_effect = execute
    with pytest.raises(ABBADeadlineExceeded):
        abba(cursor, ["Brca1"], species_ids=[1], tiers=[1], deadline=time.monotonic() + 0.5)


def test_without_a_deadline_the_pipeline_is_unchanged() -> None:
    """The worker path sets no budget: no extra statements, as before."""
    cursor = _orchestration_cursor()
    abba(cursor, ["Brca1"], species_ids=[1], tiers=[1])
    assert not any(
        c.args and c.args[0] == "SELECT set_config('statement_timeout', %s, true)"
        for c in cursor.execute.call_args_list
    )
