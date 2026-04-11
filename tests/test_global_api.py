"""
Tests for Global view API endpoints.
"""
import pytest


def test_global_overview_grouped(test_client):
    """Global overview returns instruments grouped by type."""
    resp = test_client.get("/api/global/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "groups" in data
    # Should have at least index, commodity, forex from fixtures
    types = set(data["groups"].keys())
    assert "index" in types
    assert "commodity" in types
    assert "forex" in types


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
