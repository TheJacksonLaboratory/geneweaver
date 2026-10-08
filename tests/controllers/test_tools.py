"""Tests for the tool-run endpoints."""

from unittest.mock import Mock, patch

import pytest
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


def test_upset_endpoint_merges_homologs_when_asked(client) -> None:
    """A mouse and a human set intersect on their orthologs with homology included."""
    with (
        patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=True),
        patch(
            "geneweaver.api.services.tools.db_tool_input.homologous_gene_symbols_by_geneset",
            return_value={"1": ["DRD2/Drd2"], "2": ["DRD2/Drd2"]},
        ) as merged,
    ):
        response = client.post(
            "/api/tools/upset",
            json={"geneset_ids": [1, 2], "include_homology": True},
        )
    assert response.status_code == 200
    merged.assert_called_once()
    assert response.json()["object"]["intersections"] == [{"geneset_ids": ["1", "2"], "size": 1}]


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
    # The nine registered tools, plus ABBA's search.
    assert len(tools) == 10
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


def test_a_tool_raising_indexerror_is_not_reported_as_a_missing_tool(client) -> None:
    """`IndexError` is a `LookupError`, so catching the base class mapped a bug to 404.

    That actually happened: BooleanAlgebra was handed the wrong row shape and raised
    `IndexError: list index out of range`, which the endpoint reported as 404 "no such
    tool" -- pointing a debugging effort at routing instead of at the resolver.
    """
    with (
        patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=True),
        patch(
            "geneweaver.api.services.tools.db_tool_input.gene_symbols_by_geneset",
            return_value={"1": ["A"], "2": ["B"]},
        ),
        patch(
            "geneweaver.api.services.tools.INPUT_BUILDERS",
            {"dbscan": lambda *_: (_ for _ in ()).throw(IndexError("list index out of range"))},
        ),
        pytest.raises(IndexError),
    ):
        # The generic route, not /tools/upset -- that one has its own handler and would
        # never reach the patched builder.
        client.post("/api/tools/dbscan", json={"geneset_ids": [1, 2]})


def test_an_unknown_tool_is_still_a_404(client) -> None:
    """The narrowed exception must not stop reporting a genuinely missing tool."""
    response = client.post("/api/tools/not-a-tool", json={"geneset_ids": [1, 2]})

    assert response.status_code == 404


# --- AsyncTask outcomes, as HTTP statuses ------------------------------------------

PENDING_SHAPE = {"tool": "upset", "geneset_ids": [1, 2], "gene_counts": {"1": 2}, "caveat": None}


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        ("pending", 202),
        ("sign_in", 401),
        ("bad_request", 422),
        ("failed", 502),
        ("asynctask_403", 403),
        ("asynctask_down", 502),
    ],
)
def test_run_tool_maps_asynctask_outcomes(client, raised, expected) -> None:
    """Run tool maps asynctask outcomes."""
    from geneweaver.api.services import tools as tool_service
    from geneweaver.api.services.asynctask import AsyncTaskError

    errors = {
        "pending": tool_service.ToolRunPending(PENDING_SHAPE, 11, "running"),
        "sign_in": tool_service.SignInRequired("sign in"),
        "bad_request": tool_service.ToolRequestError("two only"),
        "failed": tool_service.ToolRunFailed("failed"),
        "asynctask_403": AsyncTaskError("Unauthorized.", status_code=403),
        "asynctask_down": AsyncTaskError("unreachable"),
    }
    with (
        patch("geneweaver.api.services.tools.prepare_tool_run"),
        patch("geneweaver.api.services.tools.execute_tool_run", side_effect=errors[raised]),
    ):
        response = client.post("/api/tools/mset", json={"geneset_ids": [1, 2]})

    assert response.status_code == expected
    if raised == "pending":
        assert response.json()["object"] == {**PENDING_SHAPE, "run_id": 11, "status": "running"}


def test_get_tool_run_returns_the_run(client) -> None:
    """Get tool run returns the run."""
    run = {"run_id": 11, "status": "completed", "workflow_id": "w", "result": {"nodes": []}}
    with patch("geneweaver.api.services.tools.get_tool_run", return_value=run):
        response = client.get("/api/tools/runs/11")

    assert response.status_code == 200
    assert response.json()["object"] == run


def test_get_tool_run_passes_through_an_ownership_refusal(client) -> None:
    """Another user's run is AsyncTask's 403, not a 404 or an outage."""
    from geneweaver.api.services.asynctask import AsyncTaskError

    with patch(
        "geneweaver.api.services.tools.get_tool_run",
        side_effect=AsyncTaskError("Unauthorized.", status_code=403),
    ):
        response = client.get("/api/tools/runs/11")

    assert response.status_code == 403


def test_get_tool_run_is_404_where_asynctask_is_off(client) -> None:
    """Get tool run is 404 where asynctask is off."""
    with patch("geneweaver.api.services.tools.asynctask_configured", return_value=False):
        response = client.get("/api/tools/runs/11")

    assert response.status_code == 404


def test_upset_endpoint_reports_a_pending_run_as_202(client) -> None:
    """The typed endpoint maps AsyncTask outcomes exactly as the generic one does."""
    from geneweaver.api.services import tools as tool_service

    pending = tool_service.ToolRunPending(PENDING_SHAPE, 11, "running")
    with (
        patch("geneweaver.api.services.tools.prepare_upset"),
        patch("geneweaver.api.services.tools.execute_upset", side_effect=pending),
    ):
        response = client.post("/api/tools/upset", json={"geneset_ids": [1, 2]})

    assert response.status_code == 202
    assert response.json()["object"]["run_id"] == 11


# --- request errors are 422; only an unavailable tool is 409 -----------------------


def _readable(memberships=None):
    return (
        patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=True),
        patch(
            "geneweaver.api.services.tools.db_tool_input.gene_symbols_by_geneset",
            return_value=memberships or {"1": ["A", "B"], "2": ["B", "C"]},
        ),
    )


def test_a_malformed_dbscan_parameter_is_422_not_409(client) -> None:
    """The caller must fix it; it says nothing about the deployment."""
    readable, memberships = _readable()
    with readable, memberships:
        response = client.post(
            "/api/tools/dbscan", json={"geneset_ids": [1, 2], "parameters": {"epsilon": "x"}}
        )

    assert response.status_code == 422
    assert "dbscan" in response.json()["detail"]


def test_a_malformed_mset_parameter_is_422_and_nothing_is_submitted(client) -> None:
    """Validated against MSETInput before AsyncTask is called."""
    asynctask = Mock()
    readable, memberships = _readable()
    with (
        readable,
        memberships,
        patch("geneweaver.api.services.tools.asynctask_configured", return_value=True),
        patch("geneweaver.api.services.tools.asynctask_client_for", return_value=asynctask),
        patch(
            "geneweaver.api.services.tools.db_tool_input.species_by_geneset",
            return_value={1: 1, 2: 1},
        ),
    ):
        response = client.post(
            "/api/tools/mset",
            json={"geneset_ids": [1, 2], "parameters": {"number_of_samples": "many"}},
        )

    assert response.status_code == 422
    asynctask.submit.assert_not_called()


def test_a_tool_unavailable_here_is_409(client) -> None:
    """The one case that is a conflict with this environment rather than the request."""
    with patch("geneweaver.api.services.tools.asynctask_configured", return_value=False):
        response = client.post("/api/tools/mset", json={"geneset_ids": [1, 2]})

    assert response.status_code == 409
    assert "MSETcpp" in response.json()["detail"]


# --- the database connection is released before the run executes ------------------


@pytest.mark.parametrize(
    ("path", "prepare", "execute"),
    [
        ("/api/tools/dbscan", "prepare_tool_run", "execute_tool_run"),
        ("/api/tools/upset", "prepare_upset", "execute_upset"),
    ],
)
def test_the_connection_is_back_in_the_pool_before_execution(
    app, client, path, prepare, execute
) -> None:
    """A run may wait 30s on AsyncTask; holding the lease through it starves the pool."""
    from contextlib import contextmanager

    from geneweaver.api.dependencies import cursor_factory

    leases = {"open": 0}

    @contextmanager
    def tracked():
        leases["open"] += 1
        try:
            yield Mock()
        finally:
            leases["open"] -= 1

    def execute_checking_the_lease(prepared, runner=None):
        assert leases["open"] == 0, "a connection is still leased during execution"
        return {"ok": True}

    previous = app.dependency_overrides.get(cursor_factory)
    app.dependency_overrides[cursor_factory] = lambda: tracked
    try:
        with (
            patch(f"geneweaver.api.services.tools.{prepare}") as prepared,
            patch(
                f"geneweaver.api.services.tools.{execute}",
                side_effect=execute_checking_the_lease,
            ),
        ):
            response = client.post(path, json={"geneset_ids": [1, 2]})
    finally:
        app.dependency_overrides[cursor_factory] = previous

    assert response.status_code == 200
    prepared.assert_called_once()


# --- an analysis requires a signed-in user ----------------------------------------------


@pytest.mark.parametrize("path", ["/api/tools/upset", "/api/tools/dbscan"])
def test_anonymous_runs_are_401(app, client, path) -> None:
    """Both run endpoints refuse an anonymous caller before touching the database."""
    from geneweaver.api.dependencies import optional_full_user_released

    previous = app.dependency_overrides.get(optional_full_user_released)
    app.dependency_overrides[optional_full_user_released] = lambda: None
    try:
        with patch("geneweaver.api.services.tools.db_geneset.is_readable") as readable:
            response = client.post(path, json={"geneset_ids": [1, 2]})
    finally:
        app.dependency_overrides[optional_full_user_released] = previous

    assert response.status_code == 401
    assert "Sign in" in response.json()["detail"]
    readable.assert_not_called()


@pytest.mark.parametrize("tool", ["mset", "phenome_map"])
def test_anonymous_is_401_even_for_a_tool_unavailable_here(app, client, tool) -> None:
    """Sign-in is checked before availability, so the answer never depends on the deployment."""
    from geneweaver.api.dependencies import optional_full_user_released

    previous = app.dependency_overrides.get(optional_full_user_released)
    app.dependency_overrides[optional_full_user_released] = lambda: None
    try:
        with patch("geneweaver.api.services.tools.asynctask_configured", return_value=False):
            response = client.post(f"/api/tools/{tool}", json={"geneset_ids": [1, 2]})
    finally:
        app.dependency_overrides[optional_full_user_released] = previous

    assert response.status_code == 401


# --- an anonymous request never leases a database connection --------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [("/api/tools/upset", 401), ("/api/tools/dbscan", 401), ("/api/tools/nonexistent", 404)],
)
def test_refusals_happen_before_a_connection_is_leased(app, client, path, expected) -> None:
    """With the pool exhausted, an anonymous or unknown-tool request still gets its answer."""
    from geneweaver.api.dependencies import cursor_factory, optional_full_user_released

    def no_connections():
        raise AssertionError("a connection was leased")

    overrides = {
        optional_full_user_released: lambda: None,
        cursor_factory: lambda: no_connections,
    }
    previous = {key: app.dependency_overrides.get(key) for key in overrides}
    app.dependency_overrides.update(overrides)
    try:
        response = client.post(path, json={"geneset_ids": [1, 2]})
    finally:
        app.dependency_overrides.update(previous)

    assert response.status_code == expected


# --- ABBA ----------------------------------------------------------------------------


def test_abba_endpoint_is_not_taken_for_a_tool_name(client) -> None:
    """`/tools/abba` must reach its own route, not `/tools/{tool}`'s unknown-tool 404."""
    from geneweaver.api.schemas.tools import ABBAResult

    shaped = ABBAResult(
        parameters={},
        available_genes=1,
        available_genesets=1,
        input_species=["Mus musculus"],
        seed_genes=[],
        genesets=[],
        genes=[],
        max_occurrences=0,
        species={1: "Mus musculus"},
        tiers={1: "Tier I"},
    )
    with patch("geneweaver.api.services.abba.search", return_value=shaped) as search:
        response = client.post("/api/tools/abba", json={"genes": ["Drd2"]})
    assert response.status_code == 200
    assert response.json()["object"]["tool"] == "abba"
    assert search.call_args.args[1].genes == ["Drd2"]


def test_abba_endpoint_needs_a_seed(client) -> None:
    """No genes and no gene sets is a 422."""
    response = client.post("/api/tools/abba", json={"tiers": [1]})
    assert response.status_code == 422
    assert "at least one seed gene" in response.text


def test_abba_endpoint_requires_sign_in(app, client) -> None:
    """An anonymous search is refused with 401."""
    from geneweaver.api.dependencies import optional_full_user_released

    app.dependency_overrides[optional_full_user_released] = lambda: None
    response = client.post("/api/tools/abba", json={"genes": ["Drd2"]})
    assert response.status_code == 401


def test_abba_endpoint_refuses_an_unreadable_seed_geneset(client) -> None:
    """An unreadable seed gene set is refused with 403."""
    with patch("geneweaver.api.services.tools.db_geneset.is_readable", return_value=False):
        response = client.post("/api/tools/abba", json={"geneset_ids": [5]})
    assert response.status_code == 403


def test_abba_endpoint_answers_busy_with_retry_after(client) -> None:
    """Too many searches is a 503 the client can retry."""
    from geneweaver.api.services import abba as abba_service

    with patch.object(abba_service, "run_abba", side_effect=abba_service.ABBABusy("busy")):
        response = client.post("/api/tools/abba", json={"genes": ["Drd2"]})
    assert response.status_code == 503
    assert response.headers["retry-after"] == "60"


def test_tool_list_offers_abba(client) -> None:
    """The page builds its picker from GET /tools, so ABBA must be listed."""
    tools = client.get("/api/tools").json()["object"]["tools"]
    assert tools["abba"]["available"] is True
