"""
Tests for CLI command bar filter parsing.

Covers: valid filters, concept aliases, malformed input, suggestions.
"""
import pytest


def test_filter_single_condition(test_client):
    """Parse a single filter condition."""
    resp = test_client.post("/api/search/filter", json={
        "expression": "Filter: market cap > 50000"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["parsed_conditions"]) == 1
    assert data["parsed_conditions"][0]["concept_code"] == "market_cap"
    assert data["parsed_conditions"][0]["op"] == ">"
    assert data["parsed_conditions"][0]["value"] == 50000.0


def test_filter_multiple_conditions(test_client):
    """Parse multiple comma-separated conditions."""
    resp = test_client.post("/api/search/filter", json={
        "expression": "Filter: PE < 15, ROE > 20"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["parsed_conditions"]) == 2
    codes = {c["concept_code"] for c in data["parsed_conditions"]}
    assert "price_to_earning" in codes
    assert "roe" in codes


def test_filter_aliases(test_client):
    """Concept aliases resolve correctly."""
    resp = test_client.post("/api/search/filter", json={
        "expression": "PAT > 1000"
    })
    data = resp.json()
    assert data["parsed_conditions"][0]["concept_code"] == "net_profit"


def test_filter_debt_alias(test_client):
    """Debt alias resolves to debt_to_equity."""
    resp = test_client.post("/api/search/filter", json={
        "expression": "Debt < 0.5"
    })
    data = resp.json()
    assert data["parsed_conditions"][0]["concept_code"] == "debt_to_equity"


def test_filter_unknown_concept(test_client):
    """Unknown concept produces parse error."""
    resp = test_client.post("/api/search/filter", json={
        "expression": "Filter: xyzabc > 100"
    })
    data = resp.json()
    assert len(data["parse_errors"]) >= 1


def test_filter_malformed(test_client):
    """Malformed expression produces parse error."""
    resp = test_client.post("/api/search/filter", json={
        "expression": "Filter: hello world"
    })
    data = resp.json()
    assert data["count"] == 0


def test_filter_executes_query(test_client):
    """Filter with conditions matching sample data returns results."""
    # RELIANCE has sales = 69709.44, so sales > 50000 should match
    resp = test_client.post("/api/search/filter", json={
        "expression": "Filter: sales > 50000"
    })
    data = resp.json()
    assert data["count"] >= 1
    assert any(r["symbol"] == "RELIANCE" for r in data["results"])


def test_filter_no_match(test_client):
    """Filter that matches nothing returns empty results."""
    resp = test_client.post("/api/search/filter", json={
        "expression": "Filter: sales > 999999999"
    })
    data = resp.json()
    assert data["count"] == 0


def test_suggestions_empty(test_client):
    """Empty query returns hint."""
    resp = test_client.get("/api/search/suggestions?q=")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["suggestions"]) >= 1
    assert data["suggestions"][0]["type"] == "hint"


def test_suggestions_company(test_client):
    """Company search suggestions."""
    resp = test_client.get("/api/search/suggestions?q=rel")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["suggestions"]) >= 1
    assert data["suggestions"][0]["type"] == "company"


def test_suggestions_filter(test_client):
    """Filter concept suggestions."""
    resp = test_client.get("/api/search/suggestions?q=filter: pe")
    assert resp.status_code == 200
    data = resp.json()
    assert any(s["type"] == "concept" for s in data["suggestions"])
