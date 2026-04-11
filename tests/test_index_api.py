"""
Tests for Index deep-dive API endpoints.

Covers: constituents, movers, technicals, breadth, 404 for unknown index.
"""
import pytest


def test_index_constituents(test_client):
    """Get NIFTY 50 constituents with prices."""
    resp = test_client.get("/api/index/nifty-50/constituents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["index_name"] == "NIFTY 50"
    assert data["count"] == 2  # RELIANCE and HDFCBANK
    symbols = {c["symbol"] for c in data["constituents"]}
    assert "RELIANCE" in symbols
    assert "HDFCBANK" in symbols


def test_index_constituents_with_change(test_client):
    """Constituents include change and change_pct calculated from previous day."""
    resp = test_client.get("/api/index/nifty-50/constituents")
    data = resp.json()
    reliance = next(c for c in data["constituents"] if c["symbol"] == "RELIANCE")
    assert reliance["close"] == 1415.0
    assert reliance["change"] == 25.0  # 1415 - 1390
    assert reliance["change_pct"] == pytest.approx(1.80, abs=0.01)


def test_index_constituents_not_found(test_client):
    """Unknown index returns 404."""
    resp = test_client.get("/api/index/nonexistent-index/constituents")
    assert resp.status_code == 404


def test_index_movers(test_client):
    """Top movers returns gainers and losers."""
    resp = test_client.get("/api/index/nifty-50/movers?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert "gainers" in data
    assert "losers" in data
    # RELIANCE gained ~1.80%, HDFCBANK lost ~0.57%
    if data["gainers"]:
        assert data["gainers"][0]["symbol"] == "RELIANCE"
    if data["losers"]:
        assert data["losers"][0]["symbol"] == "HDFCBANK"


def test_index_technicals(test_client):
    """Technical indicators for index constituents."""
    resp = test_client.get("/api/index/nifty-50/technicals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["technicals"]) == 2
    reliance = next(t for t in data["technicals"] if t["symbol"] == "RELIANCE")
    assert reliance["dma_50"] == 1350.0
    assert reliance["rsi_14"] == 62.5
    assert reliance["high_52w"] == 1520.0


def test_index_breadth(test_client):
    """Index breadth based on daily_change_pct."""
    resp = test_client.get("/api/index/nifty-50/breadth")
    assert resp.status_code == 200
    data = resp.json()
    breadth = data["breadth"]
    # RELIANCE +1.80% (advance), HDFCBANK -0.57% (decline)
    assert breadth["advances"] == 1
    assert breadth["declines"] == 1


def test_instrument_price_history(test_client):
    """Price history for an instrument."""
    resp = test_client.get("/api/instrument/RELIANCE/price-history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "RELIANCE"
    assert len(data["prices"]) == 2
    # Chronological order
    assert data["prices"][0]["trade_date"] == "2026-04-09"
    assert data["prices"][1]["trade_date"] == "2026-04-10"


def test_instrument_price_history_not_found(test_client):
    """Unknown instrument returns 404."""
    resp = test_client.get("/api/instrument/NONEXISTENT/price-history")
    assert resp.status_code == 404


def test_instrument_technicals(test_client):
    """Technical indicators for an instrument."""
    resp = test_client.get("/api/instrument/RELIANCE/technicals")
    assert resp.status_code == 200
    data = resp.json()
    techs = data["technicals"]
    assert "dma_50" in techs
    assert techs["dma_50"]["value"] == 1350.0
    assert "rsi_14" in techs
