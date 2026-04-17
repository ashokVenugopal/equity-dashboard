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


class TestHeatmapTradingDayFilter:
    """Verify heatmap uses trading-day-filtered prices (from market_breadth)."""

    def test_change_pct_uses_trading_days(self, test_client):
        """change_pct should be computed from valid trading days only.
        Fixtures have breadth for 2026-04-10 and 2026-04-09 (both with advances>0).
        Prices exist for both dates. Change should reflect real trading day comparison."""
        resp = test_client.get("/api/heatmap/nifty-50")
        data = resp.json()
        for block in data["blocks"]:
            # change_pct should be non-null if 2+ trading days of prices exist
            if block["close"] is not None:
                # RELIANCE: 1390 → 1415 = +1.80%
                # HDFCBANK: 1760 → 1750 = -0.57%
                if block["symbol"] == "RELIANCE":
                    assert block["change_pct"] is not None
                    assert block["change_pct"] > 0  # went up
                elif block["symbol"] == "HDFCBANK":
                    assert block["change_pct"] is not None
                    assert block["change_pct"] < 0  # went down

    def test_heatmap_idempotent(self, test_client):
        r1 = test_client.get("/api/heatmap/nifty-50").json()
        r2 = test_client.get("/api/heatmap/nifty-50").json()
        assert r1 == r2
