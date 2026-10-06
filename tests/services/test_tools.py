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


def test_upset_request_bounds_match_the_ui() -> None:
    """The Analyze page duplicates these bounds; drift makes its message wrong.

    `ui/src/app/pages/analyze/analyze.component.ts` reports locally why a run is refused
    instead of spending a round trip on a 422. That is only correct while the two agree, and
    nothing else couples them -- so this asserts the coupling rather than trusting a comment.
    """
    from pathlib import Path

    from geneweaver.api.schemas.tools import MAX_GENESETS_WITH_ZEROS, UpSetRequest

    component = Path(__file__).parents[2] / "ui/src/app/pages/analyze/analyze.component.ts"
    if not component.is_file():
        pytest.skip("UI sources not present in this checkout")
    source = component.read_text()

    # Pydantic records the two bounds as separate `annotated_types` entries.
    bounds = {
        kind: getattr(entry, kind)
        for entry in UpSetRequest.model_fields["geneset_ids"].metadata
        for kind in ("min_length", "max_length")
        if hasattr(entry, kind)
    }
    assert set(bounds) == {"min_length", "max_length"}, (
        f"UpSetRequest.geneset_ids no longer declares both bounds: {bounds}"
    )

    for name, value in (
        ("MAX_GENESETS", bounds["max_length"]),
        ("MIN_GENESETS", bounds["min_length"]),
        ("MAX_GENESETS_WITH_ZEROS", MAX_GENESETS_WITH_ZEROS),
    ):
        assert f"const {name} = {value};" in source, (
            f"{name} in analyze.component.ts does not match the API's {value}; "
            "the page will enable or refuse runs the API disagrees with"
        )


class TestToolAvailability:
    """What the API reports it can run, which the UI's picker is built from."""

    def test_every_registered_tool_is_reported(self) -> None:
        """The picker used to list five of nine; the list must come from the registry."""
        assert len(tool_service.available_tools()) == 9
        assert set(tool_service.tool_availability()) == set(tool_service.available_tools())

    def test_the_binary_backed_tools_are_unavailable_in_process(self) -> None:
        """The API image carries no TOOLBOX binaries -- those run on the native worker."""
        availability = tool_service.tool_availability()
        for name in ("mset", "phenome_map"):
            assert availability[name]["available"] is False
            assert "AsyncTask" in availability[name]["reason"]

    def test_the_other_seven_are_available(self) -> None:
        """Pins the set, so adding a tool without a resolver fails here."""
        availability = tool_service.tool_availability()
        runnable = sorted(n for n, s in availability.items() if s["available"])
        assert runnable == [
            "boolean_algebra",
            "combine",
            "dbscan",
            "hypergeometric",
            "jaccard_clustering",
            "jaccard_similarity",
            "upset",
        ]

    def test_jaccard_similarity_carries_its_caveat(self) -> None:
        """It runs, but its p-values depend on distribution coverage."""
        state = tool_service.tool_availability()["jaccard_similarity"]
        assert state["available"] is True
        assert "p-value" in state["caveat"]

    def test_every_available_tool_has_an_input_builder(self) -> None:
        """Otherwise a run fails on the tool's own schema rather than saying why."""
        for name, state in tool_service.tool_availability().items():
            if state["available"]:
                assert name in tool_service.INPUT_BUILDERS


class TestRunToolGuards:
    """`run_tool` must refuse clearly, and must gate before doing any work."""

    def test_an_unknown_tool_raises_lookup_error(self, mock_cursor) -> None:
        """Distinct from "cannot run here" -- the endpoint maps it to 404."""
        with pytest.raises(LookupError, match="nonexistent"):
            tool_service.run_tool(mock_cursor, "nonexistent", [1, 2])

    @pytest.mark.parametrize("name", ["mset", "phenome_map"])
    def test_a_binary_backed_tool_raises_value_error(self, name: str, mock_cursor) -> None:
        """Distinct from LookupError: registered, but not runnable here (409, not 404)."""
        with pytest.raises(ValueError, match="native-worker"):
            tool_service.run_tool(mock_cursor, name, [1, 2])

    def test_an_unavailable_tool_is_refused_before_the_access_gate(self, mock_cursor) -> None:
        """No point querying readability for a run that cannot happen."""
        with (
            patch("geneweaver.api.services.tools.db_geneset.is_readable") as readable,
            pytest.raises(ValueError),
        ):
            tool_service.run_tool(mock_cursor, "mset", [1, 2])
        readable.assert_not_called()

    def test_an_unreadable_geneset_is_refused_before_the_tool_runs(self, mock_cursor) -> None:
        """The security-relevant ordering: gate, then resolve."""
        with (
            patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=False),
            patch(
                "geneweaver.api.services.tools.db_tool_input.gene_symbols_by_geneset"
            ) as resolve,
            pytest.raises(HTTPException),
        ):
            tool_service.run_tool(mock_cursor, "upset", [1, 2])
        resolve.assert_not_called()


class TestBooleanAlgebraInput:
    """BooleanAlgebra needs homology-annotated membership, not ortholog pairs.

    Getting this wrong returned zero results for every request and raised `IndexError` on a
    cross-species one, because the tool indexes columns 3 and 4 of each row.
    """

    def test_it_uses_homolog_annotations_not_homology_pairs(self, mock_cursor) -> None:
        """The two resolvers return different shapes; only one is right here."""
        rows = [[101, 5, "Abca1", 1, 379075, "GO:1"]]
        with (
            patch(
                "geneweaver.api.services.tools.db_tool_input.species_by_geneset",
                return_value={1: 1, 2: 1},
            ),
            patch(
                "geneweaver.api.services.tools.db_tool_input.homolog_annotations",
                return_value=rows,
            ) as annotations,
            patch("geneweaver.api.services.tools.db_tool_input.homology_pairs") as pairs,
        ):
            built = tool_service.INPUT_BUILDERS["boolean_algebra"](
                mock_cursor, [1, 2], {}, {"relation": "intersection"}
            )

        annotations.assert_called_once()
        pairs.assert_not_called()
        assert built["homolog_data"] == rows

    def test_rows_carry_the_six_columns_the_tool_indexes(self, mock_cursor) -> None:
        """Columns 3 (sp_id) and 4 (gs_id) are what the tool reads; 3 columns is not enough."""
        rows = [[101, 5, "Abca1", 1, 379075, "GO:1"]]
        with (
            patch(
                "geneweaver.api.services.tools.db_tool_input.species_by_geneset",
                return_value={1: 1},
            ),
            patch(
                "geneweaver.api.services.tools.db_tool_input.homolog_annotations",
                return_value=rows,
            ),
        ):
            built = tool_service.INPUT_BUILDERS["boolean_algebra"](mock_cursor, [1], {}, {})
        assert all(len(row) == 6 for row in built["homolog_data"])

    def test_species_are_deduplicated(self, mock_cursor) -> None:
        """Gene sets from one species must yield one species id, not one per gene set."""
        with (
            patch(
                "geneweaver.api.services.tools.db_tool_input.species_by_geneset",
                return_value={1: 1, 2: 1, 3: 2},
            ),
            patch(
                "geneweaver.api.services.tools.db_tool_input.homolog_annotations",
                return_value=[],
            ),
        ):
            built = tool_service.INPUT_BUILDERS["boolean_algebra"](mock_cursor, [1, 2, 3], {}, {})
        assert built["species_ids"] == [1, 2]


def test_unknown_tool_error_is_distinct_from_a_tool_crash() -> None:
    """Both are LookupError; only one means "no such tool"."""
    assert issubclass(tool_service.UnknownToolError, LookupError)
    assert not isinstance(IndexError("x"), tool_service.UnknownToolError)
