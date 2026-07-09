"""Tests for /api/macro/* (liquidity series + risk calendar)."""


def test_series_basic(test_client):
    d = test_client.get("/api/macro/series?codes=FEDFUNDS&start=2024-01-01").json()
    s = d["series"][0]
    assert s["code"] == "FEDFUNDS"
    assert len(s["points"]) == 2
    assert s["points"][-1] == {"time": "2025-02-01", "value": 4.10}


def test_series_yoy_transform(test_client):
    """CPITEST seeded 100 → 110 a year apart → YoY exactly +10%."""
    d = test_client.get(
        "/api/macro/series?codes=CPITEST&transform=yoy&start=2025-01-01").json()
    pts = d["series"][0]["points"]
    assert len(pts) == 1
    assert pts[0]["time"] == "2025-06-01"
    assert abs(pts[0]["value"] - 10.0) < 0.01


def test_series_unknown_code_empty_points(test_client):
    d = test_client.get("/api/macro/series?codes=NOSUCH").json()
    assert d["series"][0]["points"] == []


def test_series_empty_codes_400(test_client):
    assert test_client.get("/api/macro/series?codes=,,").status_code == 400


def test_events_window_and_grouping(test_client):
    d = test_client.get("/api/macro/events?days_ahead=45&days_back=0").json()
    # Two future dates seeded within 45d; the -30d event excluded by days_back=0
    assert d["total"] == 3
    assert len(d["days"]) == 2
    first = d["days"][0]
    cats = {e["category"] for e in first["events"]}
    assert cats == {"fomc", "results"}


def test_events_category_filter(test_client):
    d = test_client.get(
        "/api/macro/events?days_ahead=45&days_back=0&categories=ipo").json()
    assert d["total"] == 1
    assert d["days"][0]["events"][0]["category"] == "ipo"


def test_events_days_back_includes_past(test_client):
    d = test_client.get("/api/macro/events?days_ahead=45&days_back=45").json()
    assert d["total"] == 4
