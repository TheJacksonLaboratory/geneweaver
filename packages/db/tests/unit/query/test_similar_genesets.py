"""Similar gene sets: legacy's Jaccard over homology keys, read-only, with the run's choice."""

from geneweaver.db.query.membership import Thresholds
from geneweaver.db.query.similar_genesets import DEFAULT_LIMIT, similar_genesets


def _sql(*args, **kwargs) -> tuple[str, dict]:
    query, params = similar_genesets(*args, **kwargs)
    return " ".join(query.as_string(None).split()), params


def test_it_only_reads() -> None:
    """Legacy rewrote geneset_jaccard on every view; this never writes."""
    sql, _ = _sql(1, 0)
    for verb in ("INSERT", "UPDATE", "DELETE", "geneset_jaccard"):
        assert verb not in sql


def test_homologs_count_as_one_gene_and_genes_without_one_as_themselves() -> None:
    """Legacy's membership key (GWC-35 / G3-805), text so a negative gene id cannot collide."""
    sql, _ = _sql(1, 0)
    assert "CASE WHEN h.hom_id IS NULL THEN 'g' || gv.ode_gene_id ELSE 'h' || h.hom_id END" in sql
    assert "LEFT JOIN extsrc.homology h" in sql


def test_candidates_are_found_by_homology_group_and_by_genes_without_one() -> None:
    """hom2geneset as legacy, plus gene sets sharing a gene that has no homolog."""
    sql, _ = _sql(1, 0)
    assert "FROM extsrc.hom2geneset hg" in sql
    assert "WHERE gv.ode_gene_id IN (SELECT ode_gene_id FROM viewed WHERE hom_id IS NULL)" in sql


def test_not_itself_not_deprecated_and_only_what_the_user_may_read() -> None:
    """The viewed gene set is not listed; readability is search's, admins included."""
    sql, params = _sql(42, 7)
    assert "geneset.gs_id <> %(geneset_id)s" in sql
    assert "geneset.gs_status NOT LIKE 'de%%'" in sql
    assert "u.usr_admin > 0 AND u.usr_id = %(is_readable_by)s" in sql
    assert params["geneset_id"] == 42
    assert params["is_readable_by"] == 7


def test_every_gene_unless_a_threshold_is_chosen() -> None:
    """The same filter on both sides: the viewed gene set and every candidate."""
    sql, params = _sql(1, 0)
    assert "AND TRUE" in sql
    assert "t_number" not in params
    sql, params = _sql(1, 0, Thresholds("custom", p_value=0.01))
    assert sql.count("THEN gv.gsv_value <= %(t_p_value)s") == 2
    assert params["t_p_value"] == 0.01


def test_jaccard_over_keys_most_similar_first() -> None:
    """shared / (viewed + candidate - shared); zero overlap is not similar; top 500."""
    sql, params = _sql(1, 0)
    assert "s.shared::float / ((SELECT count(*) FROM viewed_keys) + s.genes - s.shared)" in sql
    assert "WHERE s.shared > 0" in sql
    assert "ORDER BY r.jaccard DESC, r.gs_id LIMIT %(limit)s" in sql
    assert params["limit"] == DEFAULT_LIMIT
