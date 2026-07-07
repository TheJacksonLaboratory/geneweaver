"""Unit tests for the gene-set Jaccard similarity db functions."""

from unittest.mock import MagicMock

from geneweaver.db.geneset_jaccard import calculate_jaccard, clear_jaccard
from geneweaver.db.query import geneset_jaccard as q


def _sql(builder_result) -> str:
    """Render a (SQL, params) builder result's SQL to a string for assertions."""
    return builder_result[0].as_string(None)


def test_calculate_jaccard_runs_all_steps_and_returns_count() -> None:
    """calculate_jaccard issues the 6 statements and returns the final count."""
    cursor = MagicMock()
    cursor.fetchone.return_value = [573]

    result = calculate_jaccard(cursor, 514)

    assert result == 573
    # started, clear cache, insert forward, insert reverse, completed, count
    assert cursor.execute.call_count == 6


def test_clear_jaccard_runs_two_statements() -> None:
    """clear_jaccard clears timestamps and cache."""
    cursor = MagicMock()
    clear_jaccard(cursor, 514)
    assert cursor.execute.call_count == 2


def test_insert_jaccards_forward_vs_reverse() -> None:
    """Forward compares against larger ids; reverse against smaller ids."""
    fwd_sql, fwd_params = q.insert_jaccards(514)
    rev_sql, rev_params = q.insert_jaccards(514, reverse=True)

    assert fwd_params == {"gs_id": 514, "min_jaccard": q.DEFAULT_MIN_JACCARD, "deprecated": "de%"}
    assert rev_params["gs_id"] == 514
    assert "> %(gs_id)s" in _sql((fwd_sql, fwd_params))
    assert "< %(gs_id)s" in _sql((rev_sql, rev_params))
    # forward caches (gs_id, other); reverse caches (other, gs_id)
    assert "SELECT %(gs_id)s, gs.gs_id" in " ".join(_sql((fwd_sql, fwd_params)).split())
    assert "SELECT gs.gs_id, %(gs_id)s" in " ".join(_sql((rev_sql, rev_params)).split())


def test_insert_jaccards_min_threshold_override() -> None:
    """The minimum Jaccard threshold is parameterised and overridable."""
    _, params = q.insert_jaccards(1, min_jaccard=0.1)
    assert params["min_jaccard"] == 0.1


def test_count_and_cache_clear_use_both_directions() -> None:
    """Count and cache-clear match either side of the cached pair."""
    assert "gs_id_left = %(gs_id)s OR gs_id_right = %(gs_id)s" in _sql(q.count_jaccards(1))
    assert "gs_id_left = %(gs_id)s OR gs_id_right = %(gs_id)s" in _sql(q.clear_jaccard_cache(1))
