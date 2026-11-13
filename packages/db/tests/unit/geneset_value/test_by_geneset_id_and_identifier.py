"""Test the by_geneset_id_and_identifier function."""

from geneweaver.core.enum import GeneIdentifier
from geneweaver.db.geneset_value import by_geneset_id_and_identifier

from tests.unit.testing_utils import (
    create_execute_raises_error_test,
    create_fetchall_raises_error_test,
)

test_by_geneset_id_and_identifier_execute_raises_error = create_execute_raises_error_test(
    by_geneset_id_and_identifier, 1, GeneIdentifier.GENE_SYMBOL
)
test_by_geneset_id_and_identifier_fetchall_raises_error = create_fetchall_raises_error_test(
    by_geneset_id_and_identifier, 1, GeneIdentifier.GENE_SYMBOL
)


def _without_comments(sql: str) -> str:
    """SQL with its -- comments removed (they run to the end of a line)."""
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


def _rendered_query(cursor, identifier=GeneIdentifier.ENSEMBLE_GENE) -> str:
    """The SQL the function ran, comments dropped and whitespace collapsed."""
    by_geneset_id_and_identifier(cursor, 412566, identifier)
    raw = cursor.execute.call_args.args[0].as_string(None)
    return " ".join(_without_comments(raw).split())


def _order(cursor, identifier=GeneIdentifier.ENSEMBLE_GENE) -> str:
    """The ORDER BY that picks each gene's identifier inside the DISTINCT ON (G3-836)."""
    sql = _rendered_query(cursor, identifier)
    return sql.split("ORDER BY", 1)[1].split(") gsv", 1)[0]


def test_the_identifier_is_chosen_by_an_order_not_by_chance(cursor) -> None:
    """DISTINCT ON keeps the first row of each gene, so the ORDER BY decides which one.

    It must lead with the DISTINCT ON keys (Postgres requires it), and there must be one:
    without it, GS412566's gene uploaded as ENSMUSG00000089945 came back as
    ENSMUSG00000038729.
    """
    order = _order(cursor)
    assert order.strip().startswith("g.ode_gene_id, g.gdb_id,")


def test_the_uploaded_identifier_wins(cursor) -> None:
    """A gene with several identifiers of the type: the uploaded one comes first.

    The one in gsv_source_list, compared ignoring case.
    """
    order = _order(cursor)
    assert "unnest(gsv.gsv_source_list) AS uploaded(id)" in order
    assert "lower(uploaded.id) = lower(g.ode_ref_id)" in order


def test_then_the_preferred_identifier_then_the_lowest(cursor) -> None:
    """Uploaded under another type (a symbol): the preferred one; with none, the lowest."""
    order = _order(cursor)
    uploaded = order.index("gsv_source_list")
    preferred = order.index("g.ode_pref DESC NULLS LAST")
    lowest = order.rindex("g.ode_ref_id")
    assert uploaded < preferred < lowest
    assert order.rstrip().endswith("g.ode_ref_id")


def test_the_identifier_type_is_bound_not_formatted(cursor) -> None:
    """The requested type and gene set reach the query as parameters."""
    by_geneset_id_and_identifier(cursor, 412566, GeneIdentifier.ENSEMBLE_GENE)
    params = cursor.execute.call_args.args[1]
    assert params == {"geneset_id": 412566, "gdb_id": int(GeneIdentifier.ENSEMBLE_GENE)}


def test_symbols_put_the_official_symbol_first(cursor) -> None:
    """For symbols the preferred symbol leads, ahead of an alias in the upload.

    It is the first key after the DISTINCT ON keys, so the uploaded-identifier rule only
    decides between symbols when the gene has no preferred one.
    """
    order = _order(cursor, GeneIdentifier.GENE_SYMBOL)
    official = order.index("CASE WHEN g.gdb_id = 7 AND g.ode_pref THEN 0 ELSE 1 END")
    assert official < order.index("gsv_source_list")


def test_a_gene_with_no_preferred_symbol_is_not_filtered_out(cursor) -> None:
    """The preferred symbol is chosen by the order, not by a filter.

    A WHERE on ode_pref dropped the gene from the gene set's values when none of its
    symbols was preferred (5 genes on dev, all in gene sets).
    """
    sql = _rendered_query(cursor, GeneIdentifier.GENE_SYMBOL)
    where = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
    assert "ode_pref" not in where
