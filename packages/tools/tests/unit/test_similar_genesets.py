"""Similar gene sets: the input's checks, the output's shape, and the worker's entry."""

from unittest.mock import MagicMock, patch

import pytest
from geneweaver.tools.abba.identity import sign
from geneweaver.tools.similar_genesets import TOOL_NAME, SimilarGenesetsInput
from geneweaver.tools.similar_genesets.search import shape
from geneweaver.tools.temporal import activities
from pydantic import ValidationError
from temporalio.exceptions import ApplicationError

ROW = (7, "Name", "Abbr", 2, 3, "GWAS", 13, 12, 0.923, 12, 15438)


def test_it_takes_one_gene_set_and_the_runs_thresholds() -> None:
    """Legacy's top 500 by default; the threshold choice is the tools' own."""
    request = SimilarGenesetsInput(geneset_id=5, threshold="uploader")
    assert request.limit == 500
    assert request.membership_kwargs() == {"mode": "uploader"}


@pytest.mark.parametrize("bad", [{"geneset_id": 0}, {"geneset_id": 5, "limit": 1001}])
def test_out_of_range_input_is_refused(bad) -> None:
    """No gene set 0, and no more than 1,000 back (legacy's UNION capped there)."""
    with pytest.raises(ValidationError):
        SimilarGenesetsInput(**bad)


def test_rows_are_named_for_the_page() -> None:
    """Positional rows to the fields the list and charts read."""
    out = shape([ROW], SimilarGenesetsInput(geneset_id=5), {2: "Homo sapiens"}, {3: "Tier III"})
    assert out.genes == 12
    assert out.compared == 15438
    assert out.thresholds == {"threshold": "none"}
    assert out.genesets[0].model_dump() == {
        "gs_id": 7,
        "name": "Name",
        "abbreviation": "Abbr",
        "species_id": 2,
        "tier": 3,
        "attribution": "GWAS",
        "genes": 13,
        "shared": 12,
        "jaccard": 0.923,
    }


def test_nothing_found_still_reports_the_gene_sets_size() -> None:
    """With no row to read it from, the size comes from its own query."""
    out = shape([], SimilarGenesetsInput(geneset_id=5), {}, {}, viewed=4)
    assert (out.genes, out.compared, out.genesets) == (4, 0, [])


def test_the_worker_runs_it_by_name_and_read_only(monkeypatch) -> None:
    """A database tool: no registry entry, a signed identity, a read-only connection."""
    monkeypatch.setenv("DB_PASSWORD", "secret")
    assert activities.DATABASE_TOOLS[TOOL_NAME] is activities.run_similar_genesets
    connection = MagicMock()
    connect = MagicMock()
    connect.return_value.__enter__.return_value = connection
    found = MagicMock()
    found.model_dump.return_value = {"genesets": []}
    with (
        patch("geneweaver.tools.temporal.db.connect", connect),
        patch("geneweaver.tools.similar_genesets.search.search", return_value=found) as search,
        patch.object(activities, "_heartbeating", MagicMock()),
        patch.object(activities, "activity", MagicMock()),
    ):
        out = activities.run_similar_genesets(
            {
                "tool": TOOL_NAME,
                "input": {"geneset_id": 5},
                "identity": sign(9, "secret"),
            }
        )
    assert out == {"genesets": []}
    connect.assert_called_once_with(read_only=True)
    assert search.call_args.args[2] == 9


def test_a_forged_identity_fails_the_run_without_retrying(monkeypatch) -> None:
    """Someone else's user id with a bad signature is refused, not downgraded."""
    monkeypatch.setenv("DB_PASSWORD", "secret")
    with (
        patch.object(activities, "activity", MagicMock()),
        pytest.raises(ApplicationError, match="identity signature does not verify"),
    ):
        activities.run_similar_genesets(
            {
                "tool": TOOL_NAME,
                "input": {"geneset_id": 5},
                "identity": {"user_id": 1, "signature": "forged"},
            }
        )
