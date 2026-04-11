"""
Tests for Sectors & Themes API endpoints.

Covers: performance (pivoted + filtered), constituents, 404s.
"""
import pytest


def test_sector_performance_pivoted(test_client):
    """Default performance returns pivoted rows with timeframe columns."""
    resp = test_client.get("/api/sectors/performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["classification_type"] == "sector"
    assert len(data["performance"]) == 2  # Oil & Gas and Banking Services

    oil = next(p for p in data["performance"] if p["classification_name"] == "Oil & Gas")
    assert oil["1w"] == 2.5
    assert oil["4w"] == 5.1


def test_sector_performance_filtered(test_client):
    """Performance filtered by timeframe."""
    resp = test_client.get("/api/sectors/performance?timeframe=1w")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["performance"]) == 2
    # Oil & Gas (2.5) should rank first, Banking (-1.2) second
    assert data["performance"][0]["classification_name"] == "Oil & Gas"
    assert data["performance"][0]["value"] == 2.5


def test_sector_constituents(test_client):
    """Drill-down to stocks in a sector."""
    resp = test_client.get("/api/sectors/sector/Oil & Gas/constituents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["constituents"][0]["symbol"] == "RELIANCE"


def test_sector_constituents_with_price(test_client):
    """Constituents include latest price data."""
    resp = test_client.get("/api/sectors/sector/Banking Services/constituents")
    data = resp.json()
    assert data["count"] == 1
    hdfc = data["constituents"][0]
    assert hdfc["symbol"] == "HDFCBANK"
    assert hdfc["close"] is not None


def test_sector_constituents_not_found(test_client):
    resp = test_client.get("/api/sectors/sector/NonexistentSector/constituents")
    assert resp.status_code == 404


def test_index_constituent_performance(test_client):
    """Can query performance for index_constituent type too."""
    resp = test_client.get("/api/sectors/performance?classification_type=index_constituent")
    assert resp.status_code == 200
    # No sector_performance data for index_constituent in test fixtures
    assert resp.json()["performance"] == []
