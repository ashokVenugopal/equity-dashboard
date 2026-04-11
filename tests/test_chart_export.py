"""
Tests for Chart export API.

Covers: HTML generation, data serialization, 404 for unknown instrument.
"""
import pytest


def test_chart_export_html(test_client):
    """Export chart returns valid HTML with embedded data."""
    resp = test_client.get("/api/charts/export?symbol=RELIANCE")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    html = resp.text
    assert "RELIANCE" in html
    assert "lightweight-charts" in html
    assert "createChart" in html
    # Verify data is embedded
    assert "2026-04-09" in html
    assert "2026-04-10" in html


def test_chart_export_with_dates(test_client):
    """Export chart with date range filter."""
    resp = test_client.get("/api/charts/export?symbol=RELIANCE&start_date=2026-04-10")
    assert resp.status_code == 200
    html = resp.text
    assert "2026-04-10" in html


def test_chart_export_not_found(test_client):
    """Unknown instrument returns 404."""
    resp = test_client.get("/api/charts/export?symbol=NONEXISTENT")
    assert resp.status_code == 404


def test_chart_export_index(test_client):
    """Export chart works for index instruments too."""
    resp = test_client.get("/api/charts/export?symbol=NIFTY50")
    assert resp.status_code == 200
    assert "NIFTY50" in resp.text
