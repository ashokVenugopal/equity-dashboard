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


# ═══════════════════════════════════════════════════════════════════════
# Historical change % (1W / 1M / 1Y)
# ═══════════════════════════════════════════════════════════════════════

def test_global_overview_includes_change_pct_fields(test_client):
    """Every instrument in overview exposes change_pct_1w/1m/1y keys (value may be null)."""
    resp = test_client.get("/api/global/overview")
    for instruments in resp.json()["groups"].values():
        for inst in instruments:
            assert "change_pct_1w" in inst
            assert "change_pct_1m" in inst
            assert "change_pct_1y" in inst


def test_global_overview_change_pct_computed_from_fixture(test_client):
    """BRENTUSD fixture has history at 1W/1M/1Y — pct values should match hand-computed values."""
    resp = test_client.get("/api/global/overview")
    brent = next(i for i in resp.json()["groups"]["commodity"] if i["symbol"] == "BRENTUSD")
    # latest=72.80; 1W ref=70.00 → (72.80-70.00)/70.00*100 = 4.0
    assert brent["change_pct_1w"] == pytest.approx(4.0, abs=0.01)
    # 1M ref=68.00 → (72.80-68.00)/68.00*100 = 7.058...
    assert brent["change_pct_1m"] == pytest.approx(7.0588, abs=0.01)
    # 1Y ref=60.00 → (72.80-60.00)/60.00*100 = 21.333...
    assert brent["change_pct_1y"] == pytest.approx(21.333, abs=0.01)


def test_global_overview_change_pct_null_when_no_history(test_client):
    """USDINR fixture has only the latest bar — older change_pct fields should be null."""
    resp = test_client.get("/api/global/overview")
    usd = next(i for i in resp.json()["groups"]["forex"] if i["symbol"] == "USDINR")
    assert usd["change_pct_1w"] is None
    assert usd["change_pct_1m"] is None
    assert usd["change_pct_1y"] is None


def test_global_overview_does_not_leak_internal_fields(test_client):
    """instrument_id was an internal join key — should not leak into the response."""
    resp = test_client.get("/api/global/overview")
    for instruments in resp.json()["groups"].values():
        for inst in instruments:
            assert "instrument_id" not in inst
            assert "close_1w" not in inst
            assert "close_1m" not in inst
            assert "close_1y" not in inst
