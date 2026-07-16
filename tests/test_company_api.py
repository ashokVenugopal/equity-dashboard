"""
Tests for Company API endpoints.

Covers: meta, financials pivot, ratios, shareholding, peers, search, 404s.
"""
import pytest


def test_company_meta(test_client):
    """Get company metadata."""
    resp = test_client.get("/api/company/RELIANCE")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "RELIANCE"
    assert data["name"] == "Reliance Industries"
    assert data["isin"] == "INE002A01018"
    assert any(c["classification_type"] == "sector" for c in data["classifications"])


def test_company_meta_not_found(test_client):
    resp = test_client.get("/api/company/NONEXISTENT")
    assert resp.status_code == 404


def test_company_financials(test_client):
    """Financials returns pivoted data: concepts as rows, periods as columns."""
    resp = test_client.get("/api/company/RELIANCE/financials")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "RELIANCE"
    assert "2025-03-31" in data["periods"]
    assert "profit_loss" in data["sections"]
    # Should have sales and net_profit
    pl_codes = {c["concept_code"] for c in data["sections"]["profit_loss"]}
    assert "sales" in pl_codes
    assert "net_profit" in pl_codes
    # Check value
    sales = next(c for c in data["sections"]["profit_loss"] if c["concept_code"] == "sales")
    assert sales["values"]["2025-03-31"] == 69709.44


def test_company_financials_not_found(test_client):
    resp = test_client.get("/api/company/NONEXISTENT/financials")
    assert resp.status_code == 404


def test_company_peers(test_client):
    """Peers returns same-sector companies."""
    resp = test_client.get("/api/company/RELIANCE/peers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sector"] == "Oil & Gas"
    # No other companies in Oil & Gas in test data
    assert data["peers"] == []


def test_company_peers_no_sector(test_client):
    """Company without sector returns empty peers."""
    resp = test_client.get("/api/company/TCS/peers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sector"] is None


def test_search_companies_by_symbol(test_client):
    """Search by symbol prefix."""
    resp = test_client.get("/api/search/companies?q=REL")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert data["results"][0]["symbol"] == "RELIANCE"


def test_search_companies_by_name(test_client):
    """Search by name substring."""
    resp = test_client.get("/api/search/companies?q=hdfc")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert any(r["symbol"] == "HDFCBANK" for r in data["results"])


def test_search_companies_no_results(test_client):
    resp = test_client.get("/api/search/companies?q=ZZZZZ")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_financials_grain_quarterly(test_client):
    """grain=quarterly returns only quarterly periods for P&L; sections
    with no quarterly data are absent or fall back to annual."""
    d = test_client.get("/api/company/RELIANCE/financials?grain=quarterly").json()
    assert d["grain"] == "quarterly"
    pl_periods = d["section_periods"]["profit_loss"]
    assert pl_periods == ["2025-09-30", "2025-06-30"]
    sales = next(c for c in d["sections"]["profit_loss"] if c["concept_code"] == "sales")
    assert sales["values"]["2025-09-30"] == 19000.0
    # The annual figure must NOT bleed into the quarterly view
    assert "2025-03-31" not in sales["values"]
    assert "quarterly" in d["grains_available"]["profit_loss"]


def test_financials_grain_annual_default_unchanged(test_client):
    """Default grain=annual keeps the original single-grain behavior."""
    d = test_client.get("/api/company/RELIANCE/financials").json()
    assert d["grain"] == "annual"
    sales = next(c for c in d["sections"]["profit_loss"] if c["concept_code"] == "sales")
    assert sales["values"]["2025-03-31"] == 69709.44
    assert "2025-06-30" not in sales["values"]


def test_financials_grain_validation(test_client):
    assert test_client.get("/api/company/RELIANCE/financials?grain=weekly").status_code == 422
