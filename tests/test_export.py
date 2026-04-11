"""
Tests for export API endpoints.
"""
import pytest


def _create_observation(client, ref, note="Test note"):
    return client.post("/api/observations", json={
        "data_point_ref": ref,
        "data_point_type": "fact",
        "context_json": {},
        "note": note,
    })


def test_export_observations_json(test_client):
    """Export observations as JSON."""
    _create_observation(test_client, "export:test:1", "Note 1")
    _create_observation(test_client, "export:test:2", "Note 2")

    resp = test_client.get("/api/export/observations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2


def test_export_observations_csv(test_client):
    """Export observations as CSV."""
    _create_observation(test_client, "export:csv:1", "CSV note")

    resp = test_client.get("/api/export/observations?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert "data_point_ref" in content  # CSV header
    assert "export:csv:1" in content


def test_export_observations_empty(test_client):
    """Export with no observations returns empty."""
    resp = test_client.get("/api/export/observations")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0
