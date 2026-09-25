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
