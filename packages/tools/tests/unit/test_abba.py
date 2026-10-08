"""Tests for ABBA's search, its signed identity, and its run on the tool worker."""

import threading
import time
from contextlib import contextmanager
from unittest.mock import MagicMock, Mock, patch

import pytest
from geneweaver.db.abba import ABBAResult as PipelineResult
from geneweaver.tools.abba import ABBAInput, identity
from geneweaver.tools.abba import search as abba_search
from psycopg.rows import tuple_row
from pydantic import ValidationError

SPECIES = {0: "", 1: "Mus musculus", 2: "Homo sapiens"}
TIERS = {1: "Tier I - Public Resource", 2: "Tier II - Pro-curated"}
ATTRIBUTIONS = {1: None, 8: "GO", 11: "MESH"}


def _pipeline_result() -> PipelineResult:
    """Rows in the positional shapes `geneweaver.db.abba` returns them."""
    return PipelineResult(
        available_genes=520904,
        available_genesets=222413,
        genes_of_interest=[(10, "Drd2", "Mus musculus"), (20, "DRD2", "Homo sapiens")],
        input_species=[("Mus musculus",), ("Homo sapiens",)],
        geneset_results=[
            (282317, "KEGG Neuroactive", 4, 1, 1, 12, "Neuroactive", "desc", 358),
            (5, "No source", 2, 2, 2, 1, None, None, 20),
        ],
        gene_results=[
            # The row's own ref id is an arbitrary identifier, not a symbol.
            (95197, "ENSG00000232810", "Homo sapiens", 2, 1453),
            (73850, "ANON2", "Homo sapiens", 2, 1385),
        ],
        max_occurrences=[(1453,)],
        ode_mapping={95197: ["TNF", "TNFA"], 73850: ["Anon2"]},
        preferred_mapping={95197: "TNF"},
        tier_counts={95197: {1: 2461, 2: 4501}},
        species_counts={95197: {1: 2857, 2: 7564}},
    )


def _shape(request: ABBAInput | None = None):
    request = request or ABBAInput(genes=["Drd2"])
    return abba_search.shape(
        _pipeline_result(), request, SPECIES, TIERS, {**ATTRIBUTIONS, 12: "KEGG"}
    )


# --- Shaping the pipeline's rows ------------------------------------------------------


def test_shape_names_each_gene_by_its_preferred_symbol() -> None:
    """Not the row's ref id, which is whichever identifier the join met first."""
    genes = _shape().genes
    assert genes[0].symbol == "TNF"
    assert genes[0].symbols == ["TNF", "TNFA"]
    assert genes[0].tier_counts == {1: 2461, 2: 4501}
    assert genes[0].species_counts == {1: 2857, 2: 7564}
    # No preferred symbol recorded: the first gene symbol, still not the raw ref id.
    assert genes[1].symbol == "Anon2"


def test_shape_names_gene_set_columns_and_attribution() -> None:
    """Positional gene set rows become named fields, with the source's short name."""
    first, second = _shape().genesets
    assert (first.gs_id, first.matches, first.tier, first.gene_count) == (282317, 4, 1, 358)
    assert first.attribution == "KEGG"
    # Attribution 1 is the "none" placeholder, so no badge.
    assert second.attribution is None


def test_shape_seed_species_ids_and_totals() -> None:
    """Seed genes carry species ids, for colouring by species."""
    result = _shape()
    assert [(g.symbol, g.species_id) for g in result.seed_genes] == [
        ("Drd2", 1),
        ("DRD2", 2),
    ]
    assert result.input_species == ["Homo sapiens", "Mus musculus"]
    assert result.max_occurrences == 1453
    # Species 0 has no name and is not a real species.
    assert result.species == {1: "Mus musculus", 2: "Homo sapiens"}


def test_shape_echoes_options_not_the_seed() -> None:
    """The run's options are echoed for the Run Information panel."""
    parameters = _shape(ABBAInput(genes=["Drd2"], min_genes=3)).parameters
    assert parameters == {
        "include_homology": True,
        "min_genes": 3,
        "min_genesets": None,
        "tiers": [1, 2, 3],
        "species_ids": None,
    }


def test_shape_with_no_results() -> None:
    """A search that matches nothing still shapes."""
    shaped = abba_search.shape(PipelineResult(), ABBAInput(genes=["x"]), {}, {}, {})
    assert shaped.max_occurrences == 0


def test_the_output_survives_json() -> None:
    """Temporal carries the result as JSON, whose object keys are strings."""
    dumped = _shape().model_dump(mode="json")
    assert dumped["genes"][0]["tier_counts"] == {"1": 2461, "2": 4501}
    assert type(_shape()).model_validate(dumped).genes[0].tier_counts == {1: 2461, 2: 4501}


# --- Running the pipeline -------------------------------------------------------------


def _connection():
    """A connection that hands out a tuple-row cursor for the pipeline."""
    rows = MagicMock()
    rows.fetchall.side_effect = [
        list(SPECIES.items()),
        list(TIERS.items()),
        list(ATTRIBUTIONS.items()),
    ]
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = rows
    return connection, rows


def test_search_runs_on_a_tuple_cursor_in_its_own_transaction() -> None:
    """The pipeline reads rows by position and needs its temp tables scoped."""
    connection, rows = _connection()
    with patch("geneweaver.db.abba.abba", return_value=PipelineResult()) as pipeline:
        abba_search.search(connection, ABBAInput(genes=["Drd2"]), user_id=7)

    connection.cursor.assert_called_once_with(row_factory=tuple_row)
    connection.transaction.assert_called_once()
    # The timeout is the first statement, so it bounds every pipeline query.
    first_sql, first_params = rows.execute.call_args_list[0].args
    assert "statement_timeout" in first_sql and first_params == ("240s",)
    assert pipeline.call_args.args[0] is rows


def test_search_maps_legacy_auto_and_unrestricted_species() -> None:
    """Auto and 'not restricted' become what the pipeline expects."""
    connection, _ = _connection()
    with patch("geneweaver.db.abba.abba", return_value=PipelineResult()) as pipeline:
        abba_search.search(connection, ABBAInput(genes=["Drd2"]), user_id=7)

    kwargs = pipeline.call_args.kwargs
    assert kwargs["species_ids"] == [0, 1, 2]  # unrestricted: every species
    assert kwargs["min_genes"] is None  # Auto
    assert kwargs["min_genesets"] == 0  # Auto: no floor
    assert kwargs["user_id"] == 7
    assert kwargs["tiers"] == [1, 2, 3]
    assert kwargs["include_homology"] is True
    # Seed gene sets are expanded by the API; the search never reads one itself.
    assert "geneset_ids" not in kwargs


def test_search_passes_a_restriction_and_a_timeout_through() -> None:
    """A restriction, a gene-set floor and a timeout reach the pipeline as given."""
    connection, rows = _connection()
    with patch("geneweaver.db.abba.abba", return_value=PipelineResult()) as pipeline:
        abba_search.search(
            connection,
            ABBAInput(genes=["Drd2"], species_ids=[2], min_genesets=4),
            user_id=0,
            statement_timeout_seconds=30,
        )
    assert pipeline.call_args.kwargs["species_ids"] == [2]
    assert pipeline.call_args.kwargs["min_genesets"] == 4
    assert rows.execute.call_args_list[0].args[1] == ("30s",)


@pytest.mark.parametrize(
    "body",
    [
        {"genes": ["Drd2"], "tiers": []},
        {"genes": ["Drd2"], "tiers": [6]},
        {"genes": ["Drd2"], "min_genes": 0},
        {"genes": ["Drd2"], "species_ids": []},
    ],
)
def test_input_rejects(body) -> None:
    """Options the search cannot run with are refused."""
    with pytest.raises(ValidationError):
        ABBAInput(**body)


# --- Identity -------------------------------------------------------------------------


def test_a_signed_identity_verifies() -> None:
    """The API signs; the worker, with the same secret, recovers the user."""
    assert identity.verified_user_id(identity.sign(7, "s3cret"), "s3cret") == 7


@pytest.mark.parametrize(
    "tampered",
    [
        lambda signed: {**signed, "user_id": 8},  # someone else's id
        lambda signed: {**signed, "signature": "0" * 64},
        lambda signed: identity.sign(signed["user_id"], "other-secret"),
    ],
)
def test_a_forged_identity_is_refused(tampered) -> None:
    """Submitting to AsyncTask directly must not let a user search as someone else."""
    with pytest.raises(ValueError, match="does not verify"):
        identity.verified_user_id(tampered(identity.sign(7, "s3cret")), "s3cret")


@pytest.mark.parametrize("malformed", ["7", {"user_id": "7", "signature": "x"}, {"user_id": 7}])
def test_a_malformed_identity_is_refused(malformed) -> None:
    """Only an integer user id with a signature is an identity."""
    with pytest.raises(ValueError):
        identity.verified_user_id(malformed, "s3cret")


def test_no_identity_searches_public_gene_sets_only() -> None:
    """Without an identity there is no one whose private gene sets to include."""
    assert identity.verified_user_id(None, "s3cret") == identity.PUBLIC_USER_ID == 0


def test_an_identity_without_a_key_to_check_it_is_refused() -> None:
    """A worker without the secret cannot verify, so it refuses rather than trusting."""
    with pytest.raises(ValueError, match="DB_PASSWORD"):
        identity.verified_user_id(identity.sign(7, "s3cret"), None)


# --- On the worker --------------------------------------------------------------------

pytest.importorskip("temporalio")

from geneweaver.tools.temporal import activities  # noqa: E402
from temporalio.exceptions import ApplicationError  # noqa: E402
from temporalio.testing import ActivityEnvironment  # noqa: E402


@pytest.fixture
def python_worker(monkeypatch):
    """Run as the python-profile worker, with a database password to verify against."""
    monkeypatch.setenv("GENEWEAVER_TOOLS_PROFILE", "python")
    monkeypatch.setenv("DB_PASSWORD", "s3cret")


@contextmanager
def _fake_connect(connection):
    yield connection


def test_abba_runs_on_the_python_worker_against_the_database(python_worker) -> None:
    """The activity searches with the verified user, on a writable connection."""
    connection = Mock()
    output = Mock(model_dump=Mock(return_value={"tool": "abba"}))
    envelope = {
        "tool": "abba",
        "input": {"genes": ["Drd2"]},
        "identity": identity.sign(7, "s3cret"),
    }
    with (
        patch(
            "geneweaver.tools.temporal.db.connect", return_value=_fake_connect(connection)
        ) as connect,
        patch("geneweaver.tools.abba.search.search", return_value=output) as search,
    ):
        result = ActivityEnvironment().run(activities.run_tool, envelope)

    assert result == {"tool": "abba"}
    # Temp tables: Postgres refuses CREATE in a read-only transaction, temporary or not.
    connect.assert_called_once_with(read_only=False)
    passed_connection, request, user_id = search.call_args.args
    assert passed_connection is connection
    assert request.genes == ["Drd2"]
    assert user_id == 7


@pytest.mark.parametrize(
    "envelope",
    [
        {"tool": "abba", "input": {"genes": ["Drd2"], "tiers": [9]}},
        {
            "tool": "abba",
            "input": {"genes": ["Drd2"]},
            "identity": {"user_id": 7, "signature": "x"},
        },
    ],
)
def test_a_bad_abba_request_fails_the_run_without_retrying(python_worker, envelope) -> None:
    """Bad input or a forged identity cannot become good on a retry."""
    with (
        patch("geneweaver.tools.temporal.db.connect") as connect,
        pytest.raises(ApplicationError) as failure,
    ):
        ActivityEnvironment().run(activities.run_tool, envelope)
    assert failure.value.non_retryable
    connect.assert_not_called()


def test_abba_is_served_by_the_python_profile() -> None:
    """ABBA goes to the python queue.

    The workflow AsyncTask runs routes by the `geneweaver-tools` version AsyncTask pins,
    which sends any non-native tool there; the native worker must not claim it.
    """
    from geneweaver.tools.temporal.routing import PYTHON_TASK_QUEUE, task_queue_for

    assert task_queue_for("abba") == PYTHON_TASK_QUEUE


def test_heartbeats_keep_a_long_query_alive() -> None:
    """One slow statement must not outlast the workflow's 60 s heartbeat timeout."""
    beats = []
    with (
        patch.object(activities, "_cancellation_requested", lambda: beats.append(1) or False),
        activities._heartbeating(Mock(), interval=0.01),
    ):
        time.sleep(0.1)
    assert len(beats) >= 3


def test_cancelling_a_run_cancels_its_query() -> None:
    """A cancelled run stops costing the database at once, not at its statement timeout."""
    connection = Mock(spec=["cancel"])
    cancelled = threading.Event()
    connection.cancel.side_effect = cancelled.set
    with (
        patch.object(activities, "_cancellation_requested", return_value=True),
        activities._heartbeating(connection, interval=0.01),
    ):
        assert cancelled.wait(1)
    connection.cancel.assert_called_once()
