"""GET /genesets/search: sorting and filters (G3-777), a gene and its cutoffs (G3-764)."""

from unittest.mock import patch

import pytest

SEARCH = "geneweaver.api.controller.genesets.db_search.genesets"


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"search_text": "dopamine"}, {"search_text": "dopamine"}),
        (
            {"search_text": "dopamine", "sort_by": "size", "sort_order": "desc"},
            {"sort_by": "size", "sort_order": "desc"},
        ),
        (
            {"gene": "Drd2", "p_value": "0.01", "correlation_low": "0.5"},
            {"gene": "Drd2", "p_value": 0.01, "correlation_low": 0.5, "threshold_mode": "only"},
        ),
        (
            {"gene": "Drd2", "q_value": "0.05", "threshold_mode": "first"},
            {"gene": "Drd2", "q_value": 0.05, "threshold_mode": "first"},
        ),
    ],
)
def test_the_options_reach_the_search(client, params, expected) -> None:
    """Each option is passed to the query builder, and a gene alone is a search."""
    with patch(SEARCH, return_value=[]) as search:
        response = client.get("/api/genesets/search", params=params)
    assert response.status_code == 200, response.text
    kwargs = search.call_args.kwargs
    for key, value in expected.items():
        assert kwargs[key] == value


def test_filters_combine(client) -> None:
    """Several species, tiers and score types at once, with a size range (G3-777)."""
    params = [
        ("search_text", "dopamine"),
        ("species", "Mus Musculus"),
        ("species", "Homo Sapiens"),
        ("curation_tier", "Tier II"),
        ("curation_tier", "Tier III"),
        ("score_type", "p-value"),
        ("gte_count", "10"),
        ("lte_count", "500"),
    ]
    with patch(SEARCH, return_value=[]) as search:
        response = client.get("/api/genesets/search", params=params)
    assert response.status_code == 200, response.text
    kwargs = search.call_args.kwargs
    assert {str(species) for species in kwargs["species"]} == {"Mus Musculus", "Homo Sapiens"}
    assert {str(tier) for tier in kwargs["curation_tier"]} == {"Tier II", "Tier III"}
    assert (kwargs["gte_count"], kwargs["lte_count"]) == (10, 500)


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({}, "search_text, a gene, or both"),
        ({"search_text": "   "}, "search_text, a gene, or both"),
        ({"search_text": "x", "p_value": "0.05"}, "give gene"),
        ({"gene": "Drd2", "effect_low": "2", "effect_high": "1"}, "effect_low"),
        ({"gene": "Drd2", "p_value": "2"}, "less than or equal to 1"),
        ({"search_text": "x", "sort_by": "gs_name"}, "sort_by"),
        ({"search_text": "x", "threshold_mode": "sometimes"}, "threshold_mode"),
    ],
)
def test_a_search_with_nothing_to_search_or_a_bad_option_is_refused(
    client, params, message
) -> None:
    """422 with the reason, and the database is never asked."""
    with patch(SEARCH, return_value=[]) as search:
        response = client.get("/api/genesets/search", params=params)
    assert response.status_code == 422
    assert message in response.text
    search.assert_not_called()
