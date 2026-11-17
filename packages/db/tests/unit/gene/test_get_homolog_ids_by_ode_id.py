"""Test the get_homolog_ids_by_ode_id function."""

from geneweaver.core.enum import GeneIdentifier
from geneweaver.db.gene import get_homolog_ids_by_ode_id

from tests.unit.testing_utils import (
    create_execute_raises_error_test,
    create_fetchall_raises_error_test,
)

test_get_homolog_ids_by_ode_id_execute_raises_error = create_execute_raises_error_test(
    get_homolog_ids_by_ode_id, ("1", "2"), identifier=GeneIdentifier.ENSEMBLE_GENE
)
test_get_homolog_ids_by_ode_id_fetchall_raises_error = create_fetchall_raises_error_test(
    get_homolog_ids_by_ode_id, ("1", "2"), identifier=GeneIdentifier.ENSEMBLE_GENE
)


def test_homologs_come_in_a_fixed_order(cursor) -> None:
    """By gene, then preferred identifiers, then by id (G3-836).

    A caller keeping each gene's first row keeps the same homolog on every call.
    """
    get_homolog_ids_by_ode_id(cursor, [1, 2], GeneIdentifier.GENE_SYMBOL)
    sql = " ".join(cursor.execute.call_args.args[0].split())
    assert sql.endswith("ORDER BY h.ode_gene_id, g.ode_pref DESC NULLS LAST, g.ode_ref_id;")
    assert "SELECT DISTINCT h.ode_gene_id, g.ode_ref_id, g.ode_pref" in sql
