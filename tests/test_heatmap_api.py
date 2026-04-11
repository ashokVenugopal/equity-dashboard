"""
Tests for Heatmap API endpoint.
"""
import pytest


def test_heatmap_nifty50(test_client):
    """Heatmap returns blocks with market_cap and change_pct."""
    resp = test_client.get("/api/heatmap/nifty-50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["index_name"] == "NIFTY 50"
    assert len(data["blocks"]) == 2  # RELIANCE and HDFCBANK
    for block in data["blocks"]:
        assert "symbol" in block
        assert "market_cap" in block
        assert "change_pct" in block


def test_heatmap_not_found(test_client):
    resp = test_client.get("/api/heatmap/nonexistent")
    assert resp.status_code == 404
