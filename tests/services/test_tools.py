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
        result = tool_service.run_upset(mock_cursor, [1, 2], user=Mock(), runner=runner)

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
        tool_service.run_upset(mock_cursor, [1, 2], user=Mock(), runner=runner)

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
        tool_service.run_upset(mock_cursor, [1], user=Mock(), runner=runner)

    resolve.assert_not_called()
    assert runner.tool_input is None


def test_run_upset_refuses_anonymous_callers_before_any_database_work(mock_cursor) -> None:
    """Running an analysis requires signing in; nothing is read for an anonymous caller."""
    with (
        patch("geneweaver.api.services.tools.db_geneset.is_readable") as readable,
        pytest.raises(tool_service.SignInRequired),
    ):
        tool_service.run_upset(mock_cursor, [1, 2], user=None)

    readable.assert_not_called()
    mock_cursor.assert_not_called()


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
    def test_a_binary_backed_tool_is_unavailable(self, name: str, mock_cursor) -> None:
        """Distinct from LookupError: registered, but not runnable here (409, not 404)."""
        with pytest.raises(tool_service.ToolUnavailable, match="native-worker"):
            tool_service.run_tool(mock_cursor, name, [1, 2], user=Mock())

    def test_an_unavailable_tool_is_refused_before_the_access_gate(self, mock_cursor) -> None:
        """No point querying readability for a run that cannot happen."""
        with (
            patch("geneweaver.api.services.tools.db_geneset.is_readable") as readable,
            pytest.raises(tool_service.ToolUnavailable),
        ):
            tool_service.run_tool(mock_cursor, "mset", [1, 2], user=Mock())
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
            tool_service.run_tool(mock_cursor, "upset", [1, 2], user=Mock())
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


# --- where a run executes: AsyncTask or in-process ---------------------------------


class _FakeAsyncTask:
    """Records the envelope submitted and replays a scripted outcome."""

    def __init__(self, final_status: str = "completed", result: dict | None = None) -> None:
        from geneweaver.api.services.asynctask import RunState

        self.final = RunState(run_id=11, workflow_id="ats:GeneWeaverTools:x", status=final_status)
        self.final.result = result
        self.envelope = None

    def submit(self, envelope, name):
        from geneweaver.api.services.asynctask import RunState

        self.envelope = envelope
        return RunState(run_id=11, workflow_id="ats:GeneWeaverTools:x", status="running")

    def wait(self, state, timeout, poll_interval):
        return self.final

    def get(self, run_id):
        return self.final


@pytest.fixture
def readable_memberships():
    """Every gene set readable, with two small memberships."""
    with (
        patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=True),
        patch(
            "geneweaver.api.services.tools.db_tool_input.gene_symbols_by_geneset",
            return_value=MEMBERSHIPS,
        ),
    ):
        yield


def _on_asynctask(client):
    """AsyncTask configured, with `client` standing in for the signed-in user's."""
    return (
        patch("geneweaver.api.services.tools.asynctask_configured", return_value=True),
        patch("geneweaver.api.services.tools.asynctask_client_for", return_value=client),
    )


class TestExecutionRouting:
    """Signed-in runs go to AsyncTask; anonymous ones stay in-process."""

    def test_without_asynctask_signed_in_callers_run_in_process(
        self, mock_cursor, readable_memberships
    ):
        """Environments with no AsyncTask keep the in-process path, signed-in only."""
        runner = _RecordingRunner(Mock(model_dump=Mock(return_value={"ok": True})))
        with patch("geneweaver.api.services.tools.asynctask_configured", return_value=False):
            result = tool_service.run_tool(
                mock_cursor, "upset", [1, 2], user=Mock(token="tok"), runner=runner
            )

        assert result["executed_by"] == "in_process"
        assert result["run_id"] is None
        assert result["result"] == {"ok": True}

    @pytest.mark.parametrize("configured", [True, False])
    def test_anonymous_callers_are_refused(self, configured, mock_cursor):
        """With or without AsyncTask, an analysis needs a signed-in user."""
        with (
            patch("geneweaver.api.services.tools.asynctask_configured", return_value=configured),
            patch("geneweaver.api.services.tools.db_geneset.is_readable") as readable,
            pytest.raises(tool_service.SignInRequired),
        ):
            tool_service.run_tool(mock_cursor, "upset", [1, 2], user=None)
        readable.assert_not_called()

    def test_signed_in_callers_run_on_asynctask(self, mock_cursor, readable_memberships):
        """The validated input is what crosses, in the plugin's envelope."""
        fake = _FakeAsyncTask(result={"intersections": []})
        configured, client = _on_asynctask(fake)
        with configured, client:
            result = tool_service.run_tool(mock_cursor, "upset", [1, 2], user=Mock())

        assert result["executed_by"] == "asynctask"
        assert result["run_id"] == 11
        assert result["result"] == {"intersections": []}
        assert result["gene_counts"] == {"1": 2, "2": 2}
        assert fake.envelope["tool"] == "upset"
        assert fake.envelope["input"]["gene_memberships"] == MEMBERSHIPS

    def test_a_bad_request_fails_before_submission(self, mock_cursor, readable_memberships):
        """Validated locally, so it is the tool's message now, not an opaque failed run."""
        fake = _FakeAsyncTask()
        configured, client = _on_asynctask(fake)
        with configured, client, pytest.raises(tool_service.ToolRequestError, match="dbscan"):
            tool_service.run_tool(
                mock_cursor, "dbscan", [1, 2], user=Mock(), parameters={"epsilon": "x"}
            )
        assert fake.envelope is None

    def test_a_long_run_is_handed_back_by_id(self, mock_cursor, readable_memberships):
        """A long run is handed back by id."""
        configured, client = _on_asynctask(_FakeAsyncTask(final_status="running"))
        with configured, client, pytest.raises(tool_service.ToolRunPending) as pending:
            tool_service.run_tool(mock_cursor, "upset", [1, 2], user=Mock())

        # Everything but the result, so a client polling to completion can assemble the
        # response it would have got synchronously.
        assert pending.value.body == {
            "tool": "upset",
            "geneset_ids": [1, 2],
            "gene_counts": {"1": 2, "2": 2},
            "caveat": None,
            "run_id": 11,
            "status": "running",
        }

    def test_a_failed_run_names_the_workflow(self, mock_cursor, readable_memberships):
        """AsyncTask records no cause, so the workflow id is the way to find it."""
        configured, client = _on_asynctask(_FakeAsyncTask(final_status="failed"))
        with configured, client, pytest.raises(tool_service.ToolRunFailed, match="ats:Gene"):
            tool_service.run_tool(mock_cursor, "upset", [1, 2], user=Mock())

    def test_the_gate_still_runs_first(self, mock_cursor):
        """AsyncTask knows nothing about gene set permissions; v3 must refuse first."""
        fake = _FakeAsyncTask()
        configured, client = _on_asynctask(fake)
        with (
            configured,
            client,
            patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=False),
            pytest.raises(HTTPException),
        ):
            tool_service.run_tool(mock_cursor, "upset", [1, 2], user=Mock())
        assert fake.envelope is None


def one_species(species: dict | None = None):
    """Patch the gene sets' species, all mouse unless given."""
    return patch(
        "geneweaver.api.services.tools.db_tool_input.species_by_geneset",
        return_value=species or {1: 1, 2: 1},
    )


class TestNativeTools:
    """MSET and PhenomeMap, which only AsyncTask can run."""

    def test_unavailable_where_asynctask_is_not_configured(self, mock_cursor):
        """Unavailable where asynctask is not configured."""
        with (
            patch("geneweaver.api.services.tools.asynctask_configured", return_value=False),
            pytest.raises(tool_service.ToolUnavailable, match="MSETcpp"),
        ):
            tool_service.run_tool(mock_cursor, "mset", [1, 2], user=Mock())

    def test_anonymous_callers_are_asked_to_sign_in(self, mock_cursor):
        """Anonymous callers are asked to sign in."""
        configured, client = _on_asynctask(None)
        with configured, client, pytest.raises(tool_service.SignInRequired):
            tool_service.run_tool(mock_cursor, "phenome_map", [1, 2], user=None)

    def test_mset_sends_a_universe_reference_not_the_universe(
        self, mock_cursor, readable_memberships
    ):
        """~100,000 identifiers inline would breach Temporal's 2 MiB limit (G3-784)."""
        fake = _FakeAsyncTask(result={"intersect_genes": ["B"]})
        configured, client = _on_asynctask(fake)
        with configured, client, one_species():
            tool_service.run_tool(
                mock_cursor, "mset", [1, 2], user=Mock(), parameters={"number_of_samples": 500}
            )

        # No backgrounds at all: the worker resolves them from the reference.
        assert fake.envelope == {
            "tool": "mset",
            "input": {
                "group_1_genes": ["A", "B"],
                "group_2_genes": ["B", "C"],
                "number_of_samples": 500,
                "over_representation": True,
            },
            "universe": {"geneset_ids": [1, 2]},
        }

    def test_mset_needs_exactly_two_genesets(self, mock_cursor, readable_memberships):
        """Mset needs exactly two genesets."""
        configured, client = _on_asynctask(_FakeAsyncTask())
        with configured, client, pytest.raises(tool_service.ToolRequestError, match="exactly two"):
            tool_service.run_tool(mock_cursor, "mset", [1, 2, 3], user=Mock())

    def test_mset_parses_options_rather_than_casting_them(self, mock_cursor, readable_memberships):
        """`bool("false")` is True; a cast here would silently run the opposite test."""
        fake = _FakeAsyncTask(result={})
        configured, client = _on_asynctask(fake)
        with configured, client, one_species():
            tool_service.run_tool(
                mock_cursor,
                "mset",
                [1, 2],
                user=Mock(),
                parameters={"over_representation": "false", "number_of_samples": "250"},
            )

        assert fake.envelope["input"]["over_representation"] is False
        assert fake.envelope["input"]["number_of_samples"] == 250

    @pytest.mark.parametrize(
        "parameters", [{"number_of_samples": None}, {"number_of_samples": "many"}]
    )
    def test_mset_rejects_bad_options_before_submitting(
        self, parameters, mock_cursor, readable_memberships
    ):
        """A null or non-numeric option is the caller's to fix (422), not a 500 or a 409."""
        fake = _FakeAsyncTask()
        configured, client = _on_asynctask(fake)
        with (
            configured,
            client,
            one_species(),
            pytest.raises(tool_service.ToolRequestError, match="mset"),
        ):
            tool_service.run_tool(mock_cursor, "mset", [1, 2], user=Mock(), parameters=parameters)
        assert fake.envelope is None

    def test_mset_refuses_mixed_species_before_submitting(self, mock_cursor, readable_memberships):
        """The worker's resolver would refuse it; a run that is certain to fail is not sent."""
        fake = _FakeAsyncTask()
        configured, client = _on_asynctask(fake)
        with (
            configured,
            client,
            one_species({1: 1, 2: 2}),
            pytest.raises(tool_service.ToolRequestError, match="different species"),
        ):
            tool_service.run_tool(mock_cursor, "mset", [1, 2], user=Mock())
        assert fake.envelope is None

    def test_phenome_map_rejects_bad_options_before_submitting(
        self, mock_cursor, readable_memberships
    ):
        """Validated against PhenomeMapInput here, not discovered by the worker."""
        fake = _FakeAsyncTask()
        configured, client = _on_asynctask(fake)
        with (
            configured,
            client,
            pytest.raises(tool_service.ToolRequestError, match="phenome_map"),
        ):
            tool_service.run_tool(
                mock_cursor, "phenome_map", [1, 2], user=Mock(), parameters={"min_genes": "x"}
            )
        assert fake.envelope is None

    def test_phenome_map_passes_only_its_own_options(self, mock_cursor, readable_memberships):
        """Phenome map passes only its own options."""
        fake = _FakeAsyncTask(result={"nodes": []})
        configured, client = _on_asynctask(fake)
        with configured, client:
            tool_service.run_tool(
                mock_cursor,
                "phenome_map",
                [1, 2],
                user=Mock(),
                parameters={"min_genes": 2, "unrelated": True},
            )

        assert fake.envelope["tool"] == "phenome_map"
        assert fake.envelope["input"]["gene_sets"] == MEMBERSHIPS
        assert fake.envelope["input"]["min_genes"] == 2
        assert "unrelated" not in fake.envelope["input"]

    def test_availability_follows_configuration(self):
        """Availability follows configuration."""
        with patch("geneweaver.api.services.tools.asynctask_configured", return_value=False):
            off = tool_service.tool_availability()
        with patch("geneweaver.api.services.tools.asynctask_configured", return_value=True):
            on = tool_service.tool_availability()

        assert off["mset"]["available"] is False
        assert on["mset"] == {"available": True, "reason": None, "caveat": None}
        # The pure-Python tools are available either way.
        assert off["upset"]["available"] and on["upset"]["available"]


class TestGetToolRun:
    """Polling a run by id."""

    def test_requires_asynctask(self):
        """Requires AsyncTask to be configured."""
        with (
            patch("geneweaver.api.services.tools.asynctask_configured", return_value=False),
            pytest.raises(tool_service.ToolUnavailable),
        ):
            tool_service.get_tool_run(11, user=Mock())

    def test_requires_sign_in(self):
        """Requires sign in."""
        configured, client = _on_asynctask(None)
        with configured, client, pytest.raises(tool_service.SignInRequired):
            tool_service.get_tool_run(11, user=None)

    def test_returns_status_and_result(self):
        """Returns status and result."""
        configured, client = _on_asynctask(_FakeAsyncTask(result={"nodes": []}))
        with configured, client:
            run = tool_service.get_tool_run(11, user=Mock())

        assert run == {
            "run_id": 11,
            "status": "completed",
            "workflow_id": "ats:GeneWeaverTools:x",
            "result": {"nodes": []},
        }


class TestAsyncTaskClientFor:
    """Whether a request gets an AsyncTask client, and as whom."""

    def test_none_when_not_configured(self, monkeypatch):
        """None when not configured."""
        monkeypatch.setattr(tool_service.settings, "ASYNCTASK_API_URL", None)
        assert tool_service.asynctask_client_for(Mock(token="tok")) is None

    def test_none_for_anonymous(self, monkeypatch):
        """None for anonymous."""
        monkeypatch.setattr(tool_service.settings, "ASYNCTASK_API_URL", "http://ats/api")
        assert tool_service.asynctask_client_for(None) is None

    def test_acts_as_the_user(self, monkeypatch):
        """Acts as the user."""
        monkeypatch.setattr(tool_service.settings, "ASYNCTASK_API_URL", "http://ats/api")
        client = tool_service.asynctask_client_for(Mock(token="tok"))
        assert client.base_url == "http://ats/api"
        assert client.headers == {"Authorization": "Bearer tok"}


class TestRunUpsetRouting:
    """The Analyze page's default tool routes like every other."""

    def test_signed_in_upset_runs_on_asynctask(self, mock_cursor, readable_memberships):
        """The typed result is rebuilt from AsyncTask's JSON output."""
        fake = _FakeAsyncTask(result={"intersections": [{"genesets": ["1", "2"], "size": 1}]})
        configured, client = _on_asynctask(fake)
        with configured, client:
            result = tool_service.run_upset(mock_cursor, [1, 2], user=Mock())

        assert isinstance(result, UpSetResult)
        assert [(i.geneset_ids, i.size) for i in result.intersections] == [(["1", "2"], 1)]
        assert fake.envelope["tool"] == "upset"
        assert fake.envelope["input"]["geneset_ids"] == ["1", "2"]

    def test_anonymous_upset_is_refused(self, mock_cursor, readable_memberships):
        """No user means no analysis, on either path."""
        configured, client = _on_asynctask(None)
        with configured, client, pytest.raises(tool_service.SignInRequired):
            tool_service.run_upset(mock_cursor, [1, 2], user=None)


class TestPayloadSize:
    """An oversized envelope is refused before AsyncTask sees it."""

    @pytest.mark.parametrize("tool", ["upset", "phenome_map"])
    def test_oversized_runs_are_a_request_error(self, tool, mock_cursor, readable_memberships):
        """The gene-set cap does not bound membership size, so this guard does."""
        fake = _FakeAsyncTask()
        configured, client = _on_asynctask(fake)
        with (
            configured,
            client,
            patch(
                "geneweaver.api.services.tools.check_payload_size",
                side_effect=ValueError("The payload is 3.00 MiB"),
            ),
            pytest.raises(tool_service.ToolRequestError, match=r"3\.00 MiB"),
        ):
            tool_service.run_tool(mock_cursor, tool, [1, 2], user=Mock())
        assert fake.envelope is None

    def test_the_real_guard_measures_the_envelope(self, mock_cursor):
        """Not patched: a 20-set request with large memberships trips the real limit."""
        big = {str(n): [f"GENE{i}" for i in range(20_000)] for n in range(1, 21)}
        fake = _FakeAsyncTask()
        configured, client = _on_asynctask(fake)
        with (
            configured,
            client,
            patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=True),
            patch(
                "geneweaver.api.services.tools.db_tool_input.gene_symbols_by_geneset",
                return_value=big,
            ),
            pytest.raises(tool_service.ToolRequestError, match="MiB"),
        ):
            tool_service.run_tool(mock_cursor, "upset", list(range(1, 21)), user=Mock())
        assert fake.envelope is None


class TestPrepareThenExecute:
    """The database phase and the remote phase are separable."""

    def test_execute_needs_no_cursor(self, mock_cursor, readable_memberships):
        """Everything that reads the database happens in prepare."""
        fake = _FakeAsyncTask(result={"intersections": []})
        configured, client = _on_asynctask(fake)
        with configured, client:
            prepared = tool_service.prepare_tool_run(mock_cursor, "upset", [1, 2], user=Mock())
        mock_cursor.reset_mock()

        result = tool_service.execute_tool_run(prepared)

        assert result["executed_by"] == "asynctask"
        assert mock_cursor.mock_calls == []


def test_an_unknown_tool_is_still_404_for_an_anonymous_caller(mock_cursor) -> None:
    """Unknown comes first: there is no analysis to sign in for."""
    with pytest.raises(tool_service.UnknownToolError):
        tool_service.run_tool(mock_cursor, "nonexistent", [1, 2], user=None)


@pytest.mark.parametrize("tool", ["mset", "phenome_map"])
def test_anonymous_is_refused_before_availability(tool, mock_cursor) -> None:
    """Without AsyncTask these are unavailable, but an anonymous caller hears 'sign in'."""
    with (
        patch("geneweaver.api.services.tools.asynctask_configured", return_value=False),
        pytest.raises(tool_service.SignInRequired),
    ):
        tool_service.run_tool(mock_cursor, tool, [1, 2], user=None)


class TestOptions:
    """Legacy options reach the tools, parsed strictly."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (True, True),
            (False, False),
            ("false", False),
            ("True", True),
            ("Included", True),
            ("Excluded", False),
            ("Enabled", True),
            ("Disabled", False),
            (0, False),
            (1, True),
        ],
    )
    def test_flags_parse_strictly(self, value, expected) -> None:
        """``bool("false")`` is True; this must not be."""
        assert tool_service.flag({"key": value}, "key", not expected) is expected

    @pytest.mark.parametrize("value", ["maybe", 2, None, [True]])
    def test_an_unrecognised_flag_is_a_request_error(self, value) -> None:
        """Refused, never guessed."""
        with pytest.raises(tool_service.ToolRequestError, match="key"):
            tool_service.flag({"key": value}, "key", False)

    def test_a_missing_flag_takes_the_default(self) -> None:
        """The API defaults are unchanged; the UI sends legacy's explicitly."""
        assert tool_service.flag({}, "key", True) is True

    @pytest.mark.parametrize("relation", ["union", "Intersection", "intersect", "EXCEPT"])
    def test_boolean_relations_are_accepted_case_insensitively(
        self, relation, mock_cursor
    ) -> None:
        """Legacy's spellings and the API's both work."""
        with (
            patch(
                "geneweaver.api.services.tools.db_tool_input.species_by_geneset",
                return_value={1: 1},
            ),
            patch(
                "geneweaver.api.services.tools.db_tool_input.homolog_annotations",
                return_value=[],
            ),
        ):
            built = tool_service.INPUT_BUILDERS["boolean_algebra"](
                mock_cursor, [1, 2], {}, {"relation": relation, "at_least": "3"}
            )
        assert built["relation"] == relation.lower()
        assert built["at_least"] == 3

    @pytest.mark.parametrize(
        ("parameters", "match"),
        [({"relation": "intersektion"}, "relation"), ({"at_least": 0}, "at_least")],
    )
    def test_a_bad_boolean_option_is_refused_before_any_query(
        self, parameters, match, mock_cursor
    ) -> None:
        """The tool runs anything unrecognised as an intersection; refuse it instead."""
        with (
            patch("geneweaver.api.services.tools.db_tool_input.species_by_geneset") as species,
            pytest.raises(tool_service.ToolRequestError, match=match),
        ):
            tool_service.INPUT_BUILDERS["boolean_algebra"](mock_cursor, [1, 2], {}, parameters)
        species.assert_not_called()

    def test_a_bad_relation_is_a_422_through_the_run(
        self, mock_cursor, readable_memberships
    ) -> None:
        """End to end through `run_tool`, the request error surfaces as itself."""
        with pytest.raises(tool_service.ToolRequestError, match="relation"):
            tool_service.run_tool(
                mock_cursor, "boolean_algebra", [1, 2], user=Mock(), parameters={"relation": "x"}
            )

    def test_clustering_method_is_case_insensitive(self, mock_cursor) -> None:
        """Legacy sends "Average"; the tool's schema wants lowercase."""
        built = tool_service.INPUT_BUILDERS["jaccard_clustering"](
            mock_cursor, [1, 2], MEMBERSHIPS, {"method": "Centroid"}
        )
        assert built["method"] == "centroid"

    @pytest.mark.parametrize("tool", sorted(tool_service.HOMOLOGY_TOOLS - {"phenome_map"}))
    def test_homology_merges_memberships_for_membership_tools(self, tool, mock_cursor) -> None:
        """Included: the homology resolver. Excluded (the API default): the plain one."""
        runner = _RecordingRunner(Mock(model_dump=Mock(return_value={})))
        with (
            patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=True),
            patch(
                "geneweaver.api.services.tools.db_tool_input.homologous_gene_symbols_by_geneset",
                return_value=MEMBERSHIPS,
            ) as merged,
            patch(
                "geneweaver.api.services.tools.db_tool_input.gene_symbols_by_geneset",
                return_value=MEMBERSHIPS,
            ) as plain,
            patch(
                "geneweaver.api.services.tools.db_tool_input.jaccard_distributions",
                return_value=[],
            ),
        ):
            tool_service.run_tool(
                mock_cursor,
                tool,
                [1, 2],
                user=Mock(token=None),
                parameters={"include_homology": "Included", "epsilon": 1, "min_points": 1},
                runner=runner,
            )
            merged.assert_called_once_with(mock_cursor, [1, 2])
            plain.assert_not_called()

    def test_homology_off_uses_plain_memberships(self, mock_cursor, readable_memberships) -> None:
        """A "false" string must not switch homology on."""
        runner = _RecordingRunner(Mock(model_dump=Mock(return_value={})))
        with patch(
            "geneweaver.api.services.tools.db_tool_input.homologous_gene_symbols_by_geneset"
        ) as merged:
            tool_service.run_tool(
                mock_cursor,
                "hypergeometric",
                [1, 2],
                user=Mock(token=None),
                parameters={"include_homology": "false"},
                runner=runner,
            )
        merged.assert_not_called()

    def test_a_bad_homology_value_is_refused_before_resolving(
        self, mock_cursor, readable_memberships
    ) -> None:
        """Strict parsing happens before the membership query."""
        with pytest.raises(tool_service.ToolRequestError, match="include_homology"):
            tool_service.run_tool(
                mock_cursor,
                "upset",
                [1, 2],
                user=Mock(token=None),
                parameters={"include_homology": "sometimes"},
            )

    def test_upset_endpoint_forwards_homology(self, mock_cursor) -> None:
        """The dedicated UpSet path honours the option too."""
        runner = _RecordingRunner(_Output([]))
        with (
            patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=True),
            patch(
                "geneweaver.api.services.tools.db_tool_input.homologous_gene_symbols_by_geneset",
                return_value=MEMBERSHIPS,
            ) as merged,
        ):
            tool_service.run_upset(
                mock_cursor, [1, 2], user=Mock(token=None), include_homology=True, runner=runner
            )
        merged.assert_called_once()
        assert runner.tool_input.include_homology is True

    @pytest.mark.parametrize("tool", ["jaccard_similarity", "hypergeometric"])
    def test_pairwise_deletion_queries_only_the_platforms_in_play(self, tool, mock_cursor) -> None:
        """Two mouse sets on different platforms: both platforms' genes, nothing else."""
        with (
            patch(
                "geneweaver.api.services.tools.db_tool_input.geneset_platforms",
                return_value={1: (1, 8), 2: (1, 13)},
            ),
            patch(
                "geneweaver.api.services.tools.db_tool_input.platform_gene_symbols",
                side_effect=lambda cursor, platform: {"B"} if platform == 8 else {"B", "C"},
            ) as genes,
            patch(
                "geneweaver.api.services.tools.db_tool_input.jaccard_distributions",
                return_value=[],
            ),
        ):
            built = tool_service.INPUT_BUILDERS[tool](
                mock_cursor, [1, 2], MEMBERSHIPS, {"pairwise_deletion": "Enabled"}
            )
        assert sorted(call.args[1] for call in genes.call_args_list) == [8, 13]
        pair = built["pairs"][0]
        # Only "B" is on both platforms: "A" and "C" drop out of the pair.
        if tool == "jaccard_similarity":
            assert (pair["only_i"], pair["only_j"], pair["intersection"]) == (0, 0, 1)
        else:
            assert (pair["f11"], pair["f10"], pair["f01"], pair["f00"]) == (1, 0, 0, 0)

    def test_pairwise_deletion_off_queries_nothing(self, mock_cursor) -> None:
        """The default: no platform lookups at all."""
        with (
            patch("geneweaver.api.services.tools.db_tool_input.geneset_platforms") as platforms,
            patch(
                "geneweaver.api.services.tools.db_tool_input.jaccard_distributions",
                return_value=[],
            ),
        ):
            tool_service.INPUT_BUILDERS["jaccard_similarity"](
                mock_cursor, [1, 2], MEMBERSHIPS, {"pairwise_deletion": False}
            )
        platforms.assert_not_called()
