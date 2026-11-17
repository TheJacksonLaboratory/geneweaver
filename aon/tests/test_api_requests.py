"""Test request handling fixed in the AON API (PR #42 review)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from geneweaver.aon import dependencies as deps
from geneweaver.aon.api import app
from geneweaver.aon.models import Ortholog
from geneweaver.aon.service import orthologs as orthologs_service
from sqlalchemy.orm import Query


@pytest.fixture()
def client() -> TestClient:
    """Return a client with no database: the session dependency is a mock.

    Not used as a context manager, so the lifespan (which connects) does not run.
    """
    app.dependency_overrides[deps.session] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("path", ["genes/ortholog/mapping", "genes/homolog/mapping"])
def test_mapping_without_a_gene_list_is_422(client: TestClient, path: str) -> None:
    """No body was passed to SQL as IN (None), a 500."""
    assert client.post(f"/aon/api/{path}?to_species=2").status_code == 422


def test_mapping_still_takes_a_json_list(client: TestClient) -> None:
    """The client posts the identifiers as a bare JSON list; that keeps working."""
    with patch(
        "geneweaver.aon.service.genes.map_gene_orthologs", return_value=[]
    ) as mapped:
        resp = client.post(
            "/aon/api/genes/ortholog/mapping?to_species=2&limit=30000",
            json=["MGI:1", "MGI:2"],
        )
    assert resp.status_code == 200
    assert mapped.call_args.args[1] == ["MGI:1", "MGI:2"]


@pytest.mark.parametrize("query", ["limit=-1", "start=-1"])
def test_negative_paging_is_422(client: TestClient, query: str) -> None:
    """Postgres rejects a negative LIMIT/OFFSET, which surfaced as a 500."""
    assert client.get(f"/aon/api/genes?{query}").status_code == 422


def test_possible_match_algorithms_reaches_the_service(client: TestClient) -> None:
    """The README documents the filter; the controller dropped it."""
    with patch.object(orthologs_service, "get_orthologs", return_value=[]) as get:
        resp = client.get("/aon/api/orthologs/?possible_match_algorithms=3")
    assert resp.status_code == 200
    assert get.call_args.kwargs["possible_match_algorithms"] == 3


def test_to_gene_id_filters_on_the_column() -> None:
    """``Ortholog.to_gene`` is the integer column; ``.id`` on it raised, a 500."""
    db = MagicMock()
    db.query.side_effect = lambda model: Query(model)
    captured = {}

    def keep(query: Query, start: int, limit: int) -> MagicMock:
        captured["query"] = query
        return MagicMock(all=MagicMock(return_value=[]))

    with patch.object(orthologs_service, "apply_paging", side_effect=keep):
        orthologs_service.get_orthologs(db, to_gene_id=5)
    where = str(captured["query"].whereclause)
    assert "to_gene" in where
    assert Ortholog.__tablename__ in where
