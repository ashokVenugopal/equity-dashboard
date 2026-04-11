"""
Tests for Market Overview API endpoints.

Covers: overview, flows, breadth, global, empty DB scenarios.
"""
import pytest


def test_health_check(test_client):
    """Health endpoint returns OK with DB stats."""
    resp = test_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["pipeline_db"]["connected"] is True
    assert data["pipeline_db"]["tables"]["companies"] == 3
    assert data["observations_db"]["connected"] is True


def test_market_overview(test_client):
    """Overview returns index cards, flows, and breadth."""
    resp = test_client.get("/api/market/overview")
    assert resp.status_code == 200
    data = resp.json()

    # Index cards
    assert len(data["indices"]) == 2  # NIFTY50 and BANKNIFTY
    nifty = data["indices"][0]
    assert nifty["symbol"] == "NIFTY50"
    assert nifty["close"] == 22450.0
    assert nifty["change"] == 150.0  # 22450 - 22300
    assert nifty["change_pct"] == pytest.approx(0.67, abs=0.01)

    # Flows
    assert len(data["flows"]) == 2  # FII and DII for latest date
    fii = next(f for f in data["flows"] if f["participant_type"] == "FII")
    assert fii["net_value"] == -1500.0

    # Breadth
    assert data["breadth"]["advances"] == 1200
    assert data["breadth"]["declines"] == 800


def test_market_flows_default(test_client):
    """Flows endpoint returns latest daily flows."""
    resp = test_client.get("/api/market/flows")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["flows"]) >= 2


def test_market_flows_filter_participant(test_client):
    """Flows filtered by participant_type."""
    resp = test_client.get("/api/market/flows?participant_type=FII")
    assert resp.status_code == 200
    data = resp.json()
    for flow in data["flows"]:
        assert flow["participant_type"] == "FII"


def test_market_flows_history(test_client):
    """Flow history returns time series."""
    resp = test_client.get("/api/market/flows/history?segment=CASH&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["flows"]) >= 2


def test_market_breadth(test_client):
    """Breadth endpoint returns recent data."""
    resp = test_client.get("/api/market/breadth?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["breadth"]) == 2
    assert data["breadth"][0]["trade_date"] == "2026-04-10"


def test_market_global(test_client):
    """Global endpoint returns non-stock instruments."""
    resp = test_client.get("/api/market/global")
    assert resp.status_code == 200
    data = resp.json()
    instruments = data["instruments"]
    # Should include commodity and forex, not stocks
    types = {i["instrument_type"] for i in instruments}
    assert "stock" not in types
    assert "commodity" in types or "forex" in types
