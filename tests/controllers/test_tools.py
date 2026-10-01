"""Tests for the tool-run endpoints."""

from unittest.mock import patch

from geneweaver.tools.upset import UpSet, UpSetInput

from geneweaver.api.services.tool_runner import InProcessToolRunner


def test_upset_endpoint_returns_intersections(client) -> None:
    """A permitted run returns the exclusive intersection sizes."""
    with (
        patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=True),
        patch(
            "geneweaver.api.services.tools.db_tool_input.gene_symbols_by_geneset",
            return_value={"1": ["A", "B", "C"], "2": ["B", "C", "D"]},
        ),
    ):
        response = client.post("/api/tools/upset", json={"geneset_ids": [1, 2]})

    assert response.status_code == 200
    body = response.json()["object"]
    assert body["tool"] == "UpSet"
    assert body["gene_counts"] == {"1": 3, "2": 3}
    sizes = {tuple(i["geneset_ids"]): i["size"] for i in body["intersections"]}
    # B and C are in both; A only in set 1; D only in set 2.
    assert sizes[("1", "2")] == 2
    assert sizes[("1",)] == 1
    assert sizes[("2",)] == 1


def test_upset_endpoint_refuses_unreadable_geneset(client) -> None:
    """An unreadable gene set is refused with 403, not silently omitted."""
    with patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=False):
        response = client.post("/api/tools/upset", json={"geneset_ids": [1, 2]})

    assert response.status_code == 403


def test_upset_endpoint_requires_at_least_two_genesets(client) -> None:
    """One gene set is not an intersection; the schema rejects it."""
    response = client.post("/api/tools/upset", json={"geneset_ids": [1]})
    assert response.status_code == 422


def test_upset_endpoint_caps_the_number_of_genesets(client) -> None:
    """A synchronous run is bounded; 2^n combinations grow fast."""
    response = client.post("/api/tools/upset", json={"geneset_ids": list(range(1, 25))})
    assert response.status_code == 422


def test_upset_endpoint_rejects_duplicate_genesets(client) -> None:
    """A repeated id would resolve to one membership entry while claiming two sets."""
    response = client.post("/api/tools/upset", json={"geneset_ids": [1, 1]})
    assert response.status_code == 422
    assert "Duplicate gene set ids" in response.text


def test_upset_endpoint_bounds_include_zeros(client) -> None:
    """include_zeros emits 2^n - 1 combinations, so it carries a tighter cap."""
    response = client.post(
        "/api/tools/upset",
        json={"geneset_ids": list(range(1, 13)), "include_zeros": True},
    )
    assert response.status_code == 422
    assert "include_zeros is limited to" in response.text


def test_upset_endpoint_allows_include_zeros_within_the_cap(client) -> None:
    """The cap must not block the ordinary case."""
    with (
        patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=True),
        patch(
            "geneweaver.api.services.tools.db_tool_input.gene_symbols_by_geneset",
            return_value={"1": ["A"], "2": ["B"]},
        ),
    ):
        response = client.post(
            "/api/tools/upset",
            json={"geneset_ids": [1, 2], "include_zeros": True},
        )
    assert response.status_code == 200
    # 2^2 - 1 = 3 combinations, including the empty intersection of both.
    assert len(response.json()["object"]["intersections"]) == 3


def test_in_process_runner_runs_the_real_tool() -> None:
    """The default runner executes the actual ported tool, not a stub."""
    output = InProcessToolRunner().run(
        UpSet(),
        UpSetInput(
            geneset_ids=["1", "2"],
            gene_memberships={"1": ["A", "B"], "2": ["B"]},
        ),
    )
    sizes = {tuple(i.genesets): i.size for i in output.intersections}
    assert sizes == {("1", "2"): 1, ("1",): 1}


def test_list_tools_reports_every_registered_tool(client) -> None:
    """The Analyze page builds its picker from this, so it must be complete."""
    response = client.get("/api/tools")

    assert response.status_code == 200
    tools = response.json()["object"]["tools"]
    assert len(tools) == 9
    for missing_before in (
        "boolean_algebra",
        "combine",
        "jaccard_clustering",
        "jaccard_similarity",
    ):
        assert missing_before in tools
    assert tools["mset"]["available"] is False
    assert tools["upset"]["available"] is True


def test_generic_endpoint_runs_a_tool(client) -> None:
    """DBSCAN through the generic route, with its required parameters."""
    with (
        patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=True),
        patch(
            "geneweaver.api.services.tools.db_tool_input.gene_symbols_by_geneset",
            return_value={"1": ["A", "B", "C"], "2": ["B", "C", "D"]},
        ),
    ):
        response = client.post(
            "/api/tools/dbscan",
            json={"geneset_ids": [1, 2], "parameters": {"epsilon": 1, "min_points": 2}},
        )

    assert response.status_code == 200
    body = response.json()["object"]
    assert body["tool"] == "dbscan"
    assert body["gene_counts"] == {"1": 3, "2": 3}
    assert "ran" in body["result"]


def test_generic_endpoint_refuses_a_binary_backed_tool_with_409(client) -> None:
    """Registered but not runnable here: a conflict with server state, not a bad request."""
    with patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=True):
        response = client.post("/api/tools/mset", json={"geneset_ids": [1, 2]})

    assert response.status_code == 409
    assert "native-worker" in response.json()["detail"]


def test_generic_endpoint_returns_404_for_an_unknown_tool(client) -> None:
    """A name that is not registered at all."""
    response = client.post("/api/tools/nonexistent", json={"geneset_ids": [1, 2]})

    assert response.status_code == 404


def test_generic_endpoint_refuses_unreadable_genesets(client) -> None:
    """The access gate applies to every tool, not just the UpSet route."""
    with patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=False):
        response = client.post("/api/tools/hypergeometric", json={"geneset_ids": [1, 2]})

    assert response.status_code == 403


def test_generic_endpoint_rejects_duplicate_genesets(client) -> None:
    """Duplicates would silently describe fewer gene sets than were asked for."""
    response = client.post("/api/tools/upset", json={"geneset_ids": [1, 1]})

    assert response.status_code == 422
