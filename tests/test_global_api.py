"""
Tests for Global view API endpoints.

Covers: overview (grouped), indices, commodities, forex, adrs.
Happy path, type filtering, edge cases, idempotency.
"""
import pytest


def test_global_overview_grouped(test_client):
    """Global overview returns instruments grouped by type."""
    resp = test_client.get("/api/global/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "groups" in data
    types = set(data["groups"].keys())
    assert "index" in types
    assert "commodity" in types
    assert "forex" in types


def test_global_overview_type_filtering(test_client):
    """Each group contains only instruments of that type."""
    resp = test_client.get("/api/global/overview")
    for itype, instruments in resp.json()["groups"].items():
        for inst in instruments:
            assert inst["instrument_type"] == itype


def test_global_overview_no_stocks(test_client):
    """Overview excludes stock instruments."""
    resp = test_client.get("/api/global/overview")
    assert "stock" not in resp.json()["groups"]


def test_global_indices(test_client):
    """Indices endpoint returns only indices."""
    resp = test_client.get("/api/global/indices")
    assert resp.status_code == 200
    data = resp.json()
    assert data["instrument_type"] == "index"
    for inst in data["instruments"]:
        assert "symbol" in inst and "close" in inst


def test_global_commodities(test_client):
    """Commodities endpoint returns only commodities."""
    resp = test_client.get("/api/global/commodities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["instrument_type"] == "commodity"
    assert len(data["instruments"]) >= 1
    assert data["instruments"][0]["symbol"] == "BRENTUSD"


def test_global_forex(test_client):
    """Forex endpoint returns only forex."""
    resp = test_client.get("/api/global/forex")
    assert resp.status_code == 200
    data = resp.json()
    assert data["instrument_type"] == "forex"
    assert len(data["instruments"]) >= 1


def test_global_adrs_empty(test_client):
    """ADRs returns empty if no ADR instruments in fixtures."""
    resp = test_client.get("/api/global/adrs")
    assert resp.status_code == 200
    assert resp.json()["instruments"] == []


def test_global_all_idempotent(test_client):
    """All global endpoints are idempotent."""
    for endpoint in ["/api/global/overview", "/api/global/indices",
                     "/api/global/commodities", "/api/global/forex", "/api/global/adrs"]:
        r1 = test_client.get(endpoint).json()
        r2 = test_client.get(endpoint).json()
        assert r1 == r2, f"{endpoint} not idempotent"
