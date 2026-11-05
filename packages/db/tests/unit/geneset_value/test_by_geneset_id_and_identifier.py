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


def _rendered_query(cursor) -> str:
    """The SQL the function ran, whitespace collapsed."""
    by_geneset_id_and_identifier(cursor, 412566, GeneIdentifier.ENSEMBLE_GENE)
    query = cursor.execute.call_args.args[0]
    return " ".join(query.as_string(None).split())


def _order(cursor) -> str:
    """The ORDER BY that picks each gene's identifier inside the DISTINCT ON (G3-836)."""
    sql = _rendered_query(cursor)
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
