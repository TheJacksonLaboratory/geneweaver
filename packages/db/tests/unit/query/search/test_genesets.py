"""The gene set search query: sorting (G3-777), the gene and its cutoffs (G3-764)."""

import pytest
from geneweaver.db.query.search import search
from psycopg.sql import Composed, Identifier


def _render(composable) -> str:
    """Render SQL without a connection, quoting identifiers itself."""
    if isinstance(composable, Identifier):
        return '"' + '"."'.join(composable._obj) + '"'
    if isinstance(composable, Composed):
        return "".join(_render(part) for part in composable)
    return composable.as_string(None)


def _sql(**kwargs) -> tuple[str, dict]:
    query, params = search.genesets(**kwargs)
    # The query's parts are joined with spaces, so a comma can stand alone: " , ".
    return " ".join(_render(query).split()).replace(" , ", ", "), params


def test_an_unsorted_search_is_still_in_id_order_so_pages_do_not_overlap() -> None:
    """With no sort, the id: unordered pages repeated and skipped gene sets on dev."""
    sql, params = _sql(search_text="dopamine", is_readable_by=0)
    assert "JOIN geneset_search" in sql
    assert sql.endswith("ORDER BY geneset.gs_id + 0 LIMIT 25 OFFSET 0")
    assert params["search"] == "dopamine"


@pytest.mark.parametrize("key", sorted(search.SORT_COLUMNS))
@pytest.mark.parametrize("order", ["asc", "desc"])
def test_sorting_uses_only_listed_columns_then_the_id(key, order) -> None:
    """A sort key selects a fixed fragment; the id breaks ties, so paging is stable."""
    sql, _ = _sql(search_text="x", sort_by=key, sort_order=order)
    expected = _render(search.SORT_COLUMNS[key])
    assert (
        f"ORDER BY {' '.join(expected.split())} {order.upper()} NULLS LAST, geneset.gs_id + 0"
        in sql
    )


def test_an_unlisted_sort_key_is_refused() -> None:
    """Never formatted in: an unknown key fails rather than reaching the SQL."""
    with pytest.raises(KeyError):
        search.genesets(search_text="x", sort_by="gs_name; DROP TABLE geneset")


def test_a_gene_alone_skips_the_search_view_and_binds_the_gene() -> None:
    """Gene-only searches need neither the text index nor publication fields."""
    sql, params = _sql(gene="Drd2", is_readable_by=0)
    assert "geneset_search" not in sql
    assert "lower(g.ode_ref_id) = lower(%(gene)s)" in sql
    assert params["gene"] == "Drd2"
    assert "gsv_value" not in sql  # No cutoffs: holding the gene is enough.


def test_cutoffs_are_an_or_across_score_types_each_with_its_own_rule() -> None:
    """p/q at most their cutoff; correlation/effect inside their range, either end open."""
    sql, params = _sql(
        gene="Drd2", p_value=0.01, q_value=0.05, correlation_low=0.5, effect_high=-1.0
    )
    assert "(geneset.gs_threshold_type = 1 AND gsv.gsv_value <= %(p_value)s)" in sql
    assert "(geneset.gs_threshold_type = 2 AND gsv.gsv_value <= %(q_value)s)" in sql
    assert "(geneset.gs_threshold_type = 4 AND gsv.gsv_value >= %(correlation_low)s)" in sql
    assert "(geneset.gs_threshold_type = 5 AND gsv.gsv_value <= %(effect_high)s)" in sql
    assert sql.count(" OR (geneset.gs_threshold_type") == 3
    assert params | {"p_value": 0.01, "q_value": 0.05} == params
    assert params["correlation_low"] == 0.5
    assert params["effect_high"] == -1.0
    assert "correlation_high" not in params


def test_a_closed_range_needs_both_ends() -> None:
    """Both ends given: the value must lie between them."""
    sql, _ = _sql(gene="Drd2", correlation_low=-0.9, correlation_high=-0.5)
    assert (
        "(geneset.gs_threshold_type = 4 AND gsv.gsv_value >= %(correlation_low)s "
        "AND gsv.gsv_value <= %(correlation_high)s)" in sql
    )


def test_only_mode_filters_by_the_cutoffs() -> None:
    """The default keeps only the gene sets where the gene's score passes."""
    sql, _ = _sql(gene="Drd2", p_value=0.01)
    where, order = sql.split("WHERE", 1)[1].split("ORDER BY")
    assert "gsv.gsv_value <= %(p_value)s" in where
    assert "gsv_value" not in order


def test_first_mode_keeps_every_gene_set_holding_it_and_puts_passing_ones_first() -> None:
    """Passing first, then the chosen sort, then the id."""
    sql, _ = _sql(gene="Drd2", p_value=0.01, threshold_mode="first", sort_by="name")
    where, order = sql.split("WHERE", 1)[1].split("ORDER BY")
    assert "gsv_value" not in where
    assert order.strip().startswith("EXISTS")
    assert "gsv.gsv_value <= %(p_value)s" in order
    assert order.index("DESC") < order.index("lower(geneset.gs_name)")
    assert order.rstrip().endswith("geneset.gs_id + 0 LIMIT 25 OFFSET 0")


def test_readability_is_the_functions_cases_set_based() -> None:
    """The user's groups, shared projects and admin flag are looked up once, not per row."""
    sql, params = _sql(search_text="x", is_readable_by=7)
    assert params["is_readable_by"] == 7
    for case in (
        "geneset.usr_id = %(is_readable_by)s",
        "geneset.gs_groups = '0'",
        "geneset.cur_id < 5",
        "FROM production.usr2grp u2g WHERE u2g.usr_id = %(is_readable_by)s",
        "FROM production.project2geneset p2g",
        "u.usr_admin > 0",
    ):
        assert case in sql
    assert "geneset_is_readable2" not in sql


def test_no_reader_no_readability_filter() -> None:
    """As before: no reader given, no filter."""
    sql, params = _sql(search_text="x")
    assert "is_readable_by" not in params
    assert "usr2grp" not in sql


def test_no_cutoffs_no_threshold_predicate() -> None:
    """A gene with no cutoffs only has to be held."""
    predicate, params = search.gene_threshold_filter()
    assert predicate is None
    assert params == {}
