"""
Tests for Observation Logging API.

Covers: create, read, update (upsert), delete, history tracking, idempotency.
"""
import pytest


def _create_observation(client, ref="fact:RELIANCE:sales:2025-03-31:annual:consolidated",
                        note="Revenue looks strong"):
    return client.post("/api/observations", json={
        "data_point_ref": ref,
        "data_point_type": "fact",
        "context_json": {"company": "RELIANCE", "concept": "sales"},
        "note": note,
        "tags": "bullish,earnings",
    })


def test_create_observation(test_client):
    """Create a new observation."""
    resp = _create_observation(test_client)
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"


def test_get_observation(test_client):
    """Retrieve a created observation."""
    _create_observation(test_client)
    resp = test_client.get("/api/observations/fact:RELIANCE:sales:2025-03-31:annual:consolidated")
    assert resp.status_code == 200
    data = resp.json()
    assert data["observation"]["note"] == "Revenue looks strong"
    assert data["observation"]["tags"] == "bullish,earnings"
    assert data["history"] == []  # No history yet


def test_update_observation_creates_history(test_client):
    """Updating an observation archives the previous note."""
    ref = "fact:RELIANCE:sales:2025-03-31:annual:consolidated"
    _create_observation(test_client, ref=ref, note="First note")

    # Update with new note
    resp = test_client.post("/api/observations", json={
        "data_point_ref": ref,
        "data_point_type": "fact",
        "context_json": {"company": "RELIANCE", "concept": "sales"},
        "note": "Updated note after earnings",
        "tags": "bullish,revised",
    })
    assert resp.json()["status"] == "updated"

    # Check history
    resp = test_client.get(f"/api/observations/{ref}")
    data = resp.json()
    assert data["observation"]["note"] == "Updated note after earnings"
    assert len(data["history"]) == 1
    assert data["history"][0]["previous_note"] == "First note"


def test_upsert_idempotency(test_client):
    """Creating the same observation twice results in update, not duplicate."""
    ref = "fact:TCS:net_profit:2025-03-31:annual:consolidated"
    _create_observation(test_client, ref=ref, note="Note v1")
    _create_observation(test_client, ref=ref, note="Note v2")
    _create_observation(test_client, ref=ref, note="Note v3")

    # Should have one observation with two history entries
    resp = test_client.get(f"/api/observations/{ref}")
    data = resp.json()
    assert data["observation"]["note"] == "Note v3"
    assert len(data["history"]) == 2


def test_list_observations(test_client):
    """List all observations."""
    _create_observation(test_client, ref="fact:A:sales:2025:annual:c", note="A")
    _create_observation(test_client, ref="fact:B:sales:2025:annual:c", note="B")

    resp = test_client.get("/api/observations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2


def test_list_observations_filter_type(test_client):
    """List observations filtered by type."""
    _create_observation(test_client, ref="fact:A:x:y:z:c", note="A")
    test_client.post("/api/observations", json={
        "data_point_ref": "price:RELIANCE:2025-04-10:close",
        "data_point_type": "price",
        "context_json": {},
        "note": "Price note",
    })

    resp = test_client.get("/api/observations?data_point_type=price")
    data = resp.json()
    assert data["count"] == 1
    assert data["observations"][0]["data_point_type"] == "price"


def test_list_observations_filter_tags(test_client):
    """Filter observations by tag."""
    _create_observation(test_client, ref="fact:A:x:y:z:c", note="A")  # tags: "bullish,earnings"
    test_client.post("/api/observations", json={
        "data_point_ref": "fact:B:x:y:z:c",
        "data_point_type": "fact",
        "context_json": {},
        "note": "B",
        "tags": "red-flag",
    })

    resp = test_client.get("/api/observations?tags=red-flag")
    data = resp.json()
    assert data["count"] == 1


def test_delete_observation(test_client):
    """Delete an observation and its history."""
    ref = "fact:DELETE:me:2025:annual:c"
    _create_observation(test_client, ref=ref, note="To delete")

    resp = test_client.delete(f"/api/observations/{ref}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Verify gone
    resp = test_client.get(f"/api/observations/{ref}")
    assert resp.status_code == 404


def test_get_nonexistent_observation(test_client):
    """Getting a nonexistent observation returns 404."""
    resp = test_client.get("/api/observations/does:not:exist")
    assert resp.status_code == 404


def test_delete_nonexistent_observation(test_client):
    """Deleting a nonexistent observation returns 404."""
    resp = test_client.delete("/api/observations/does:not:exist")
    assert resp.status_code == 404
