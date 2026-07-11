"""User-preferences key/value API."""


def test_pref_roundtrip(test_client):
    # Unset key → null value
    d = test_client.get("/api/prefs/volume-profiler:placement").json()
    assert d == {"key": "volume-profiler:placement", "value": None}

    r = test_client.put("/api/prefs/volume-profiler:placement",
                        json={"value": "gutter"})
    assert r.status_code == 200
    assert test_client.get("/api/prefs/volume-profiler:placement").json()["value"] == "gutter"

    # Upsert overwrites
    test_client.put("/api/prefs/volume-profiler:placement", json={"value": "overlay"})
    assert test_client.get("/api/prefs/volume-profiler:placement").json()["value"] == "overlay"


def test_pref_validation(test_client):
    assert test_client.put("/api/prefs/ok-key", json={"value": ""}).status_code == 400
    assert test_client.put("/api/prefs/ok-key", json={"value": 42}).status_code == 400
    assert test_client.put("/api/prefs/bad key!", json={"value": "x"}).status_code == 400
    assert test_client.get("/api/prefs/bad key!").status_code == 400
    assert test_client.put("/api/prefs/ok-key", json={"value": "x" * 513}).status_code == 400
