"""The gene set search query.

Sorting (G3-777), genes and their cutoffs (G3-764, G3-832), homologs (G3-834).
"""

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


def _where_and_order(sql: str) -> tuple[str, str]:
    """The outer query's WHERE and ORDER BY, past the result columns' own subqueries."""
    body = sql.split(" FROM geneset ", 1)[1]
    where, order = body.split("WHERE", 1)[1].split("ORDER BY")
    return where, order


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
    where, _ = _where_and_order(sql)
    assert "gsv_value" not in where  # No cutoffs: holding the gene is enough.


def test_cutoffs_are_an_or_across_score_types_each_with_its_own_rule() -> None:
    """p/q at most their cutoff; correlation/effect inside their range, either end open."""
    sql, params = _sql(
        gene="Drd2", p_value=0.01, q_value=0.05, correlation_low=0.5, effect_high=-1.0
    )
    where, _ = _where_and_order(sql)
    assert "(geneset.gs_threshold_type = 1 AND gsv.gsv_value <= %(p_value)s)" in where
    assert "(geneset.gs_threshold_type = 2 AND gsv.gsv_value <= %(q_value)s)" in where
    assert "(geneset.gs_threshold_type = 4 AND gsv.gsv_value >= %(correlation_low)s)" in where
    assert "(geneset.gs_threshold_type = 5 AND gsv.gsv_value <= %(effect_high)s)" in where
    assert where.count(" OR (geneset.gs_threshold_type") == 3
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
    where, order = _where_and_order(sql)
    assert "gsv.gsv_value <= %(p_value)s" in where
    assert "gsv_value" not in order


def test_first_mode_keeps_every_gene_set_holding_it_and_puts_passing_ones_first() -> None:
    """Passing first, then the chosen sort, then the id."""
    sql, _ = _sql(gene="Drd2", p_value=0.01, threshold_mode="first", sort_by="name")
    where, order = _where_and_order(sql)
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
        # Admins and curators see private gene sets in search, as in legacy.
        "u.usr_admin > 0",
    ):
        assert case in sql
    assert "geneset_is_readable2" not in sql


def test_a_gene_set_can_be_looked_up_by_id_under_the_same_rule() -> None:
    """How a typed id is checked: one gene set, filtered as any search is."""
    sql, params = _sql(gs_id=51, is_readable_by=7)
    assert "geneset.gs_id = %(gs_id)s" in sql
    assert params["gs_id"] == 51
    assert "geneset.usr_id = %(is_readable_by)s" in sql
    assert "geneset_search" not in sql  # No text, so no search view.


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


def _count_sql(**kwargs) -> tuple[str, dict]:
    query, params = search.count_genesets(**kwargs)
    return " ".join(_render(query).split()).replace(" , ", ", "), params


@pytest.mark.parametrize(
    "kwargs",
    [
        {"search_text": "alcohol OR cocaine", "is_readable_by": 7},
        {"gene": "Drd2", "p_value": 0.05, "species": None, "gte_count": 10},
        {"gene": "Drd2", "p_value": 0.05, "threshold_mode": "first"},
        {"gene": ["Drd2", "Tp53"], "gene_match": "any", "homology": True, "p_value": 0.05},
        {"gene": ["Drd2", "Tp53"], "p_value": 0.05, "threshold_mode": "first"},
        {"gs_id": 51, "is_readable_by": 0},
    ],
)
def test_the_count_matches_the_same_rows_as_the_pages(kwargs) -> None:
    """Counted over the page query's own joins and WHERE, so the total cannot drift."""
    page, page_params = _sql(**kwargs)
    count, count_params = _count_sql(**kwargs)
    # Past the result columns (a gene search's have subqueries of their own), up to the
    # outer ORDER BY, which is the query's last.
    page_matches = page.split(" FROM geneset ", 1)[1].rsplit(" ORDER BY ", 1)[0]
    assert count == "SELECT count(*) AS total FROM geneset " + page_matches
    assert count_params == page_params


def test_the_count_ignores_paging_and_sorting() -> None:
    """The API passes its page and sort through; none of it changes how many match."""
    count, _ = _count_sql(
        search_text="dopamine", limit=50, offset=100, sort_by="size", sort_order="desc"
    )
    for clause in ("ORDER BY", "LIMIT", "OFFSET", "gs_count"):
        assert clause not in count


# --- several genes (G3-832) ----------------------------------------------------------------


def test_several_genes_each_bind_their_own_parameter() -> None:
    """One EXISTS per gene, each over its own bound identifier; none formatted in."""
    sql, params = _sql(gene=["Drd2", "Tp53"])
    where, _ = _where_and_order(sql)
    assert params["gene_0"] == "Drd2"
    assert params["gene_1"] == "Tp53"
    assert "gene" not in params
    assert where.count("EXISTS (SELECT 1 FROM extsrc.geneset_value gsv") == 2
    assert "lower(%(gene_0)s)" in where
    assert "lower(%(gene_1)s)" in where
    assert "Drd2" not in sql


def test_one_gene_in_a_list_is_the_single_gene_search() -> None:
    """``gene=["Drd2"]`` builds exactly what ``gene="Drd2"`` does."""
    assert _sql(gene=["Drd2"]) == _sql(gene="Drd2")


@pytest.mark.parametrize(("match", "joiner"), [("all", " AND "), ("any", " OR ")])
def test_all_needs_every_gene_and_any_needs_one(match, joiner) -> None:
    """``all`` joins the genes' EXISTS with AND, ``any`` with OR."""
    sql, _ = _sql(gene=["Drd2", "Tp53"], gene_match=match)
    where, _ = _where_and_order(sql)
    assert f"){joiner}EXISTS (SELECT 1 FROM extsrc.geneset_value gsv" in where


def test_all_is_the_default() -> None:
    """Without gene_match, a gene set must hold every gene."""
    assert _sql(gene=["Drd2", "Tp53"]) == _sql(gene=["Drd2", "Tp53"], gene_match="all")


def test_an_unknown_gene_match_is_refused() -> None:
    """Never silently treated as one or the other."""
    with pytest.raises(ValueError, match="gene_match"):
        search.genesets(gene=["Drd2", "Tp53"], gene_match="most")


def test_too_many_genes_are_refused() -> None:
    """Each gene adds a lookup on geneset_value, so the count is capped."""
    with pytest.raises(ValueError, match=f"At most {search.MAX_GENES}"):
        search.genesets(gene=[f"G{i}" for i in range(search.MAX_GENES + 1)])


def test_the_cutoffs_apply_to_each_gene() -> None:
    """One set of cutoffs, inside every gene's EXISTS, so each gene's own score must pass."""
    sql, _ = _sql(gene=["Drd2", "Tp53"], p_value=0.05)
    where, _ = _where_and_order(sql)
    assert where.count("gsv.gsv_value <= %(p_value)s") == 2


def test_first_mode_with_several_genes_orders_by_how_many_pass() -> None:
    """Every gene set holding the genes; those where all pass lead, then fewer."""
    sql, _ = _sql(gene=["Drd2", "Tp53"], p_value=0.05, threshold_mode="first")
    where, order = _where_and_order(sql)
    assert "gsv_value" not in where
    assert order.strip().startswith("((EXISTS")
    assert order.count(")::int") == 2
    assert ")::int + (EXISTS" in order


# --- homologs (G3-834) ---------------------------------------------------------------------


def test_without_homology_only_the_gene_itself_matches() -> None:
    """The query-builder default: no homology table, as before."""
    sql, _ = _sql(gene="Drd2")
    assert "homology" not in sql


def test_homology_widens_each_gene_to_its_homology_groups() -> None:
    """As ABBA: the gene's hom_ids, then every gene sharing them, any species."""
    sql, _ = _sql(gene=["Tp53", "Drd2"], homology=True)
    where, _ = _where_and_order(sql)
    for key in ("gene_0", "gene_1"):
        assert (
            f"lower(g.ode_ref_id) = lower(%({key})s) UNION SELECT h2.ode_gene_id "
            "FROM extsrc.homology h1 JOIN extsrc.homology h2 ON h2.hom_id = h1.hom_id "
            f"WHERE h1.ode_gene_id IN (SELECT g.ode_gene_id FROM extsrc.gene g "
            f"WHERE lower(g.ode_ref_id) = lower(%({key})s))"
        ) in where


def test_homology_cutoffs_apply_to_the_matching_genes_score() -> None:
    """The cutoff sits inside the EXISTS over the widened genes: whichever gene matched."""
    sql, _ = _sql(gene="Tp53", homology=True, p_value=0.05)
    where, _ = _where_and_order(sql)
    assert "extsrc.homology" in where
    assert "gsv.gsv_value <= %(p_value)s" in where


# --- which gene matched (G3-834) -----------------------------------------------------------


def test_a_gene_search_says_which_gene_each_result_matched() -> None:
    """A ``matched_genes`` column, one entry per searched gene the gene set holds."""
    sql, _ = _sql(gene=["Tp53", "Drd2"], homology=True)
    columns = sql.split(" FROM geneset ", 1)[0]
    assert columns.endswith("WHERE m IS NOT NULL) AS matched_genes")
    assert columns.count("jsonb_build_object('query'") == 2
    assert "'homolog', gsv.ode_gene_id NOT IN" in columns
    assert f"sym.gdb_id = {search._GENE_SYMBOL_GDB_ID} AND sym.ode_pref" in columns


def test_the_matched_gene_prefers_one_that_passes_then_the_typed_gene() -> None:
    """A stable choice: passing the cutoffs, then not a homolog, then by symbol."""
    sql, _ = _sql(gene="Tp53", homology=True, p_value=0.05)
    columns = sql.split(" FROM geneset ", 1)[0]
    order = columns.split("ORDER BY", 1)[1]
    assert order.index("gsv.gsv_value <= %(p_value)s") < order.index("(gsv.ode_gene_id IN")
    assert order.index("(gsv.ode_gene_id IN") < order.index("sym.ode_ref_id LIMIT 1")


def test_a_search_without_a_gene_has_no_matched_genes_column() -> None:
    """Text and id searches return the gene set columns only, as before."""
    sql, _ = _sql(search_text="dopamine")
    assert "matched_genes" not in sql
