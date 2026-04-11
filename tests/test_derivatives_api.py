"""
Tests for Derivatives API endpoints.

Covers: PCR, FII positioning, OI changes, participant data.
"""
import pytest


def test_pcr(test_client):
    """Put-Call Ratio from options chain data."""
    resp = test_client.get("/api/derivatives/pcr?instrument=NIFTY")
    assert resp.status_code == 200
    data = resp.json()
    assert data["instrument"] == "NIFTY"
    assert len(data["pcr_data"]) > 0
    row = data["pcr_data"][0]
    assert "put_oi" in row
    assert "call_oi" in row
    assert "pcr" in row
    # Total put OI = 5M + 3M = 8M, total call OI = 6M + 4M = 10M, PCR = 0.8
    assert row["put_oi"] == 8000000
    assert row["call_oi"] == 10000000
    assert row["pcr"] == pytest.approx(0.8, abs=0.001)


def test_fii_positioning(test_client):
    """FII long/short positioning."""
    resp = test_client.get("/api/derivatives/fii-positioning")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["positioning"]) > 0
    idx_futures = next(p for p in data["positioning"] if p["instrument_category"] == "INDEX_FUTURES")
    assert idx_futures["long_contracts"] == 120000
    assert idx_futures["short_contracts"] == 180000
    # long_pct = 120000 / 300000 * 100 = 40.0
    assert idx_futures["long_pct"] == pytest.approx(40.0, abs=0.1)
    assert idx_futures["short_pct"] == pytest.approx(60.0, abs=0.1)


def test_oi_changes(test_client):
    """Series OI data."""
    resp = test_client.get("/api/derivatives/oi-changes?instrument=NIFTY")
    assert resp.status_code == 200
    data = resp.json()
    assert data["instrument"] == "NIFTY"
    assert len(data["oi_data"]) > 0
    row = data["oi_data"][0]
    assert row["total_oi"] == 26500000


def test_participant_positioning(test_client):
    """All participants for a given date."""
    resp = test_client.get("/api/derivatives/participant/2026-04-10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == "2026-04-10"
    assert len(data["positioning"]) == 2  # INDEX_FUTURES and INDEX_OPTIONS


def test_participant_positioning_empty_date(test_client):
    """Date with no data returns empty list."""
    resp = test_client.get("/api/derivatives/participant/2020-01-01")
    assert resp.status_code == 200
    assert len(resp.json()["positioning"]) == 0
