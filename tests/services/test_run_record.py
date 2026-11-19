"""A run's request, kept as its AsyncTask input description (G3-801)."""

import json

import pytest

from geneweaver.api.services.run_record import RECORD_KEY, RECORD_VERSION, RunRecord


def test_a_record_survives_the_round_trip() -> None:
    """Written as the description, read back the same."""
    record = RunRecord(
        tool="abba", geneset_ids=[5, 6], request={"genes": ["Drd2"], "geneset_ids": [5, 6]}
    )
    assert RunRecord.from_description(record.to_description()) == record


def test_the_description_is_marked_and_versioned() -> None:
    """So a later format can tell this one apart, and free text is not mistaken for it."""
    data = json.loads(RunRecord(tool="upset", geneset_ids=[1]).to_description())
    assert data[RECORD_KEY] == RECORD_VERSION


@pytest.mark.parametrize(
    "description",
    [
        None,
        "",
        "my notes about this run",
        "{not json " + RECORD_KEY,
        json.dumps([RECORD_KEY]),
        json.dumps({RECORD_KEY: 99, "tool": "upset", "geneset_ids": [1], "request": {}}),
        json.dumps({RECORD_KEY: 1, "tool": 5, "geneset_ids": [1], "request": {}}),
        json.dumps({RECORD_KEY: 1, "tool": "upset", "geneset_ids": ["1"], "request": {}}),
        json.dumps({RECORD_KEY: 1, "tool": "upset", "geneset_ids": [True], "request": {}}),
        json.dumps({RECORD_KEY: 1, "tool": "upset", "geneset_ids": [1], "request": []}),
    ],
)
def test_anything_else_is_no_record_rather_than_an_error(description) -> None:
    """A description this code did not write must not break a user's run list."""
    assert RunRecord.from_description(description) is None
