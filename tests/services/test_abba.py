"""Tests for the ABBA search service."""

import threading
from contextlib import nullcontext
from unittest.mock import MagicMock, Mock, patch

import pytest
from geneweaver.db.abba import ABBAResult as PipelineResult
from psycopg.rows import tuple_row
from pydantic import ValidationError

from geneweaver.api.schemas.tools import ABBARequest
from geneweaver.api.services import abba as service
from geneweaver.api.services.tools import SignInRequired

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


def _shape(request: ABBARequest | None = None):
    request = request or ABBARequest(genes=["Drd2"])
    return service.shape(_pipeline_result(), request, SPECIES, TIERS, {**ATTRIBUTIONS, 12: "KEGG"})


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
    parameters = _shape(ABBARequest(genes=["Drd2"], min_genes=3)).parameters
    assert parameters == {
        "include_homology": True,
        "min_genes": 3,
        "min_genesets": None,
        "tiers": [1, 2, 3],
        "species_ids": None,
    }


def test_shape_with_no_results() -> None:
    """A search that matches nothing still shapes."""
    assert (
        service.shape(PipelineResult(), ABBARequest(genes=["x"]), {}, {}, {}).max_occurrences == 0
    )


def _connection():
    """A dict-row cursor whose connection hands out a tuple-row cursor for the pipeline."""
    rows = MagicMock()
    rows.fetchall.side_effect = [
        list(SPECIES.items()),
        list(TIERS.items()),
        list(ATTRIBUTIONS.items()),
    ]
    cursor = MagicMock()
    cursor.connection.cursor.return_value.__enter__.return_value = rows
    return cursor, rows


def test_search_runs_on_a_tuple_cursor_in_its_own_transaction() -> None:
    """The pipeline reads rows by position and needs its temp tables scoped."""
    cursor, rows = _connection()
    with patch.object(service, "abba", return_value=PipelineResult()) as pipeline:
        service.search(cursor, ABBARequest(genes=["Drd2"]), user_id=7)

    cursor.connection.cursor.assert_called_once_with(row_factory=tuple_row)
    cursor.connection.transaction.assert_called_once()
    # The timeout is the first statement, so it bounds every pipeline query.
    first_sql, first_params = rows.execute.call_args_list[0].args
    assert "statement_timeout" in first_sql and first_params == ("240s",)
    assert pipeline.call_args.args[0] is rows


def test_search_maps_legacy_auto_and_unrestricted_species() -> None:
    """Auto and 'not restricted' become what the pipeline expects."""
    cursor, _ = _connection()
    with patch.object(service, "abba", return_value=PipelineResult()) as pipeline:
        service.search(cursor, ABBARequest(genes=["Drd2"]), user_id=7)

    kwargs = pipeline.call_args.kwargs
    assert kwargs["species_ids"] == [0, 1, 2]  # unrestricted: every species
    assert kwargs["min_genes"] is None  # Auto
    assert kwargs["min_genesets"] == 0  # Auto: no floor
    assert kwargs["user_id"] == 7
    assert kwargs["tiers"] == [1, 2, 3]
    assert kwargs["include_homology"] is True


def test_search_passes_a_species_restriction_through() -> None:
    """A restriction and a gene-set floor reach the pipeline as given."""
    cursor, _ = _connection()
    with patch.object(service, "abba", return_value=PipelineResult()) as pipeline:
        service.search(
            cursor, ABBARequest(genes=["Drd2"], species_ids=[2], min_genesets=4), user_id=7
        )
    assert pipeline.call_args.kwargs["species_ids"] == [2]
    assert pipeline.call_args.kwargs["min_genesets"] == 4


def test_anonymous_is_refused_before_a_connection_is_leased() -> None:
    """Running a search requires signing in, checked before the pool is touched."""
    open_cursor = Mock()
    with pytest.raises(SignInRequired):
        service.run_abba(open_cursor, ABBARequest(genes=["Drd2"]), user=None)
    open_cursor.assert_not_called()


def test_a_search_over_the_limit_is_refused_not_queued() -> None:
    """A search past the limit must not wait on the pool."""
    open_cursor = Mock()
    full = threading.BoundedSemaphore(1)
    full.acquire()
    with patch.object(service, "_running", full), pytest.raises(service.ABBABusy):
        service.run_abba(open_cursor, ABBARequest(genes=["Drd2"]), user=Mock())
    open_cursor.assert_not_called()


def test_the_slot_is_released_when_a_search_fails() -> None:
    """A failed search must not leak its slot."""
    slot = threading.BoundedSemaphore(1)
    with (
        patch.object(service, "_running", slot),
        patch.object(service, "_gate_geneset_access"),
        patch.object(service, "search", side_effect=RuntimeError("query failed")),
        pytest.raises(RuntimeError),
    ):
        service.run_abba(lambda: nullcontext(Mock()), ABBARequest(genes=["Drd2"]), Mock())
    assert slot.acquire(blocking=False)


def test_seed_gene_sets_are_access_gated() -> None:
    """Seed gene sets must be readable by the caller."""
    with (
        patch.object(service, "_gate_geneset_access") as gate,
        patch.object(service, "search", return_value="result"),
    ):
        service.run_abba(
            lambda: nullcontext("cursor"), ABBARequest(geneset_ids=[5, 6]), user=Mock()
        )
    assert gate.call_args.args[0] == "cursor"
    assert gate.call_args.args[2] == [5, 6]


@pytest.mark.parametrize(
    "body",
    [
        {},  # no seed at all
        {"genes": ["  ", ""]},  # blanks are not a seed
        {"genes": ["Drd2"], "tiers": []},
        {"genes": ["Drd2"], "tiers": [6]},
        {"genes": ["Drd2"], "min_genes": 0},
        {"genes": ["Drd2"], "min_genesets": 0},
        {"genes": ["Drd2"], "species_ids": []},
    ],
)
def test_request_rejects(body) -> None:
    """Requests the search cannot run are refused."""
    with pytest.raises(ValidationError):
        ABBARequest(**body)


def test_request_cleans_genes_case_insensitively() -> None:
    """Repeats and blanks are dropped; tiers are normalised."""
    request = ABBARequest(genes=[" Drd2", "drd2", "Drd1", ""], tiers=[3, 1, 1])
    assert request.genes == ["Drd2", "Drd1"]
    assert request.tiers == [1, 3]


def test_request_accepts_gene_sets_alone() -> None:
    """A gene set alone is a valid seed."""
    assert ABBARequest(geneset_ids=[167180]).genes == []
