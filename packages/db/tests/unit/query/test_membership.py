"""A run's threshold choice: which of a gene set's genes take part (curation, 2026-10-16)."""

import pytest
from geneweaver.db.query.membership import ALL_GENES, Thresholds, membership_filter


def _sql(thresholds: Thresholds, **aliases) -> tuple[str, dict]:
    query, params = membership_filter(thresholds, **aliases)
    return " ".join(query.as_string(None).split()), params


def test_every_gene_is_the_default() -> None:
    """A gene set is not inherently thresholded: no choice, no filter."""
    assert ALL_GENES.mode == "none"
    assert _sql(ALL_GENES) == ("TRUE", {})


def test_uploader_reads_each_stored_cutoff_with_at_most() -> None:
    """p/q at most the stored cutoff (curation: <=), ranges inclusive, binary keeps all."""
    sql, params = _sql(Thresholds("uploader"))
    assert "WHEN gs.gs_threshold_type IN (1, 2) AND gs.gs_threshold ~ %(t_number)s" in sql
    assert "THEN gv.gsv_value <= gs.gs_threshold::numeric" in sql
    assert "BETWEEN split_part(gs.gs_threshold, ',', 1)::numeric" in sql
    assert "WHEN gs.gs_threshold_type = 3 THEN TRUE" in sql
    assert sql.endswith("ELSE gv.gsv_in_threshold END)")
    assert set(params) == {"t_number"}


@pytest.mark.parametrize(
    ("text", "readable"),
    [("0.05", True), (".5", True), ("1e-5", True), (" 0.001 ", True), ("Nan", False), ("", False)],
)
def test_a_cutoff_is_cast_only_when_it_reads_as_a_number(text, readable) -> None:
    """Guards each cast, so a stored 'Nan' falls back to the flag instead of failing a run."""
    import re

    _, params = _sql(Thresholds("uploader"))
    assert bool(re.match(params["t_number"], text)) is readable


def test_custom_cutoffs_apply_per_score_type_and_others_keep_every_gene() -> None:
    """Only the types given are cut; binary and the rest keep every gene."""
    sql, params = _sql(
        Thresholds("custom", p_value=0.01, correlation_low=-0.5, correlation_high=0.5)
    )
    assert "WHEN gs.gs_threshold_type = 1 THEN gv.gsv_value <= %(t_p_value)s" in sql
    assert (
        "WHEN gs.gs_threshold_type = 4 THEN gv.gsv_value >= %(t_correlation_low)s "
        "AND gv.gsv_value <= %(t_correlation_high)s" in sql
    )
    assert "gs_threshold_type = 2" not in sql
    assert sql.endswith("ELSE TRUE END)")
    assert params == {"t_p_value": 0.01, "t_correlation_low": -0.5, "t_correlation_high": 0.5}


def test_custom_with_no_cutoff_is_every_gene() -> None:
    """Custom without a cutoff cuts nothing."""
    assert _sql(Thresholds("custom")) == ("TRUE", {})


def test_aliases_follow_the_query() -> None:
    """Each query names its own geneset_value and geneset aliases."""
    sql, _ = _sql(Thresholds("custom", q_value=0.05), gv="gv2", gs="gs2")
    assert "WHEN gs2.gs_threshold_type = 2 THEN gv2.gsv_value <= %(t_q_value)s" in sql


def test_an_unknown_mode_is_refused() -> None:
    """Only none, uploader and custom exist."""
    with pytest.raises(ValueError, match="mode"):
        Thresholds("sometimes")
