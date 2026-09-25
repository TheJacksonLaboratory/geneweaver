"""Tests for the tool-run service layer.

The access gate is the security-relevant part: the tools know nothing about users, so if
this layer does not refuse unreadable gene sets, a caller can read a gene set through a
tool result that they could not read directly.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from geneweaver.api.schemas.tools import UpSetResult
from geneweaver.api.services import tools as tool_service


class _Output:
    """Stand-in for UpSetOutput."""

    def __init__(self, intersections) -> None:
        self.intersections = intersections


class _Intersection:
    def __init__(self, genesets, size) -> None:
        self.genesets = genesets
        self.size = size


class _RecordingRunner:
    """Captures the input a tool would have been run with."""

    def __init__(self, output) -> None:
        self.output = output
        self.tool = None
        self.tool_input = None

    def run(self, tool, tool_input):
        self.tool = tool
        self.tool_input = tool_input
        return self.output


MEMBERSHIPS = {"1": ["A", "B"], "2": ["B", "C"]}


@pytest.fixture
def mock_cursor() -> Mock:
    """A stand-in cursor; every DB call in these tests is patched out."""
    return Mock()


def test_run_upset_gates_then_resolves_then_runs(mock_cursor) -> None:
    """A permitted run resolves memberships and maps the tool's output."""
    runner = _RecordingRunner(_Output([_Intersection(["1", "2"], 1)]))
    with (
        patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=True),
        patch(
            "geneweaver.api.services.tools.db_tool_input.gene_symbols_by_geneset",
            return_value=MEMBERSHIPS,
        ),
    ):
        result = tool_service.run_upset(mock_cursor, [1, 2], user=None, runner=runner)

    assert isinstance(result, UpSetResult)
    assert result.tool == "UpSet"
    assert result.geneset_ids == [1, 2]
    assert result.gene_counts == {"1": 2, "2": 2}
    assert [(i.geneset_ids, i.size) for i in result.intersections] == [(["1", "2"], 1)]
    # Gene set ids reach the tool as strings, which is what UpSetInput declares.
    assert runner.tool_input.geneset_ids == ["1", "2"]
    assert runner.tool_input.gene_memberships == MEMBERSHIPS


def test_run_upset_refuses_unreadable_genesets(mock_cursor) -> None:
    """An unreadable gene set is a 403, naming the offending ids."""
    runner = _RecordingRunner(_Output([]))
    with (
        patch(
            "geneweaver.api.services.tools.db_geneset.is_readable",
            side_effect=[True, False],
        ),
        pytest.raises(HTTPException) as exc,
    ):
        tool_service.run_upset(mock_cursor, [1, 2], user=None, runner=runner)

    assert exc.value.status_code == 403
    assert "2" in exc.value.detail


def test_run_upset_does_not_run_the_tool_when_refused(mock_cursor) -> None:
    """The gate runs before anything is resolved or executed."""
    runner = _RecordingRunner(_Output([]))
    with (
        patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=False),
        patch("geneweaver.api.services.tools.db_tool_input.gene_symbols_by_geneset") as resolve,
        pytest.raises(HTTPException),
    ):
        tool_service.run_upset(mock_cursor, [1], user=None, runner=runner)

    resolve.assert_not_called()
    assert runner.tool_input is None


def test_run_upset_anonymous_uses_public_user_id(mock_cursor) -> None:
    """An anonymous caller is checked as user 0, the public audience."""
    runner = _RecordingRunner(_Output([]))
    with (
        patch(
            "geneweaver.api.services.tools.db_geneset.is_readable", return_value=True
        ) as readable,
        patch(
            "geneweaver.api.services.tools.db_tool_input.gene_symbols_by_geneset",
            return_value={"1": []},
        ),
    ):
        tool_service.run_upset(mock_cursor, [1], user=None, runner=runner)

    assert readable.call_args.args[1] == 0
