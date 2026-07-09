"""
Tests for /api/index-history/* (catalog, series overlay, range stats,
equal-weight baskets). Leans on the RISKCO fixture: ~1y of weekday
closes ramping 800 → 1000 with the final close at 900.
"""


def test_catalog_groups_and_baskets(test_client):
    d = test_client.get("/api/index-history/catalog").json()
    assert "instruments" in d and "baskets" in d
    stock_syms = {i["symbol"] for i in d["instruments"].get("stock", [])}
    assert "RISKCO" in stock_syms  # has 200+ price rows
    assert isinstance(d["baskets"], list)


def test_series_normalized_rebases_to_100(test_client):
    d = test_client.get("/api/index-history/series?symbols=RISKCO&range=1y").json()
    assert d["normalized"] is True
    pts = d["series"][0]["points"]
    assert len(pts) > 100
    assert pts[0]["value"] == 100.0
    # Ramp is upward then final dip to 900 — last normalized value ≈
    # 900 / first-in-window close × 100, strictly above 100.
    assert pts[-1]["value"] > 100.0


def test_series_raw_prices_when_normalize_false(test_client):
    d = test_client.get(
        "/api/index-history/series?symbols=RISKCO&range=1y&normalize=false").json()
    pts = d["series"][0]["points"]
    assert pts[-1]["value"] == 900.0


def test_series_caps_at_four_symbols(test_client):
    d = test_client.get(
        "/api/index-history/series?symbols=RISKCO,RELIANCE,HDFCBANK,TCS,NIFTY50").json()
    assert len(d["series"]) <= 4


def test_series_unknown_symbol_404(test_client):
    resp = test_client.get("/api/index-history/series?symbols=NOSUCH")
    assert resp.status_code == 404


def test_stats_windows_and_distances(test_client):
    d = test_client.get("/api/index-history/stats?symbols=RISKCO").json()
    s = d["stats"][0]
    assert s["available"] is True
    assert s["last"] == 900.0
    # All-time = full seeded ramp: low 800 (day 0), high ~1000 (peak)
    assert s["alltime"]["low"] == 800.0
    assert 995.0 <= s["alltime"]["high"] <= 1000.0
    assert s["alltime"]["off_high_pct"] <= -9.0  # 900 vs ~1000 → ~-10%
    assert s["alltime"]["off_low_pct"] == 12.5   # 900 vs 800
    # 52W window trims the earliest days of the ~380-day ramp, so its
    # low sits above the all-time low.
    assert s["w52"]["low"] > 800.0
    assert s["first_date"] < s["last_date"]


def test_stats_unknown_symbol_404(test_client):
    assert test_client.get("/api/index-history/stats?symbols=NOSUCH").status_code == 404


def test_basket_unknown_404(test_client):
    resp = test_client.get(
        "/api/index-history/basket?classification_type=theme&name=NoSuchTheme")
    assert resp.status_code == 404


def test_empty_symbols_400(test_client):
    assert test_client.get("/api/index-history/series?symbols=").status_code == 400
    assert test_client.get("/api/index-history/stats?symbols=,,").status_code == 400


# ---------------------------------------------------------------------------
# Custom indices (user-defined, stored in observations DB)
# ---------------------------------------------------------------------------


def test_custom_index_crud_roundtrip(test_client):
    # Create
    r = test_client.post("/api/index-history/custom",
                         json={"name": "My Pair", "symbols": ["RISKCO", "RISKCO2"]})
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["symbols"] == ["RISKCO", "RISKCO2"]
    cid = created["id"]

    # List
    listed = test_client.get("/api/index-history/custom").json()["custom_indices"]
    assert any(c["id"] == cid and c["name"] == "My Pair" for c in listed)

    # Update
    r = test_client.put(f"/api/index-history/custom/{cid}",
                        json={"name": "My Pair v2", "symbols": ["RISKCO", "RISKCO2"]})
    assert r.status_code == 200
    assert r.json()["name"] == "My Pair v2"

    # Delete
    assert test_client.delete(f"/api/index-history/custom/{cid}").status_code == 200
    listed = test_client.get("/api/index-history/custom").json()["custom_indices"]
    assert not any(c["id"] == cid for c in listed)


def test_custom_index_validation(test_client):
    # Too few symbols
    r = test_client.post("/api/index-history/custom",
                         json={"name": "One", "symbols": ["RISKCO"]})
    assert r.status_code == 400
    # Unknown symbol
    r = test_client.post("/api/index-history/custom",
                         json={"name": "Ghost", "symbols": ["RISKCO", "NOSUCHSYM"]})
    assert r.status_code == 400
    assert "NOSUCHSYM" in r.json()["detail"]
    # Bad name
    r = test_client.post("/api/index-history/custom",
                         json={"name": "", "symbols": ["RISKCO", "RISKCO2"]})
    assert r.status_code == 400


def test_custom_index_duplicate_name_409(test_client):
    payload = {"name": "Dup Basket", "symbols": ["RISKCO", "RISKCO2"]}
    assert test_client.post("/api/index-history/custom", json=payload).status_code == 200
    r = test_client.post("/api/index-history/custom", json=payload)
    assert r.status_code == 409
    # cleanup so other tests see a clean list
    listed = test_client.get("/api/index-history/custom").json()["custom_indices"]
    for c in listed:
        if c["name"] == "Dup Basket":
            test_client.delete(f"/api/index-history/custom/{c['id']}")


def test_custom_index_series_equal_weight(test_client):
    r = test_client.post("/api/index-history/custom",
                         json={"name": "EW Test", "symbols": ["RISKCO", "RISKCO2"]})
    cid = r.json()["id"]
    d = test_client.get(f"/api/index-history/custom/{cid}/series?range=1y").json()
    assert d["members_used"] == 2
    assert len(d["points"]) > 20
    # Basket days require both members reporting. RISKCO2 exists only for
    # the last ~60 days, and each member rebases at its OWN first in-window
    # date — so the first basket point is the mean of (RISKCO already partway
    # up its ramp, RISKCO2 at 100), not 100. Sanity-band the ends.
    assert 95.0 < d["points"][0]["value"] < 125.0
    assert 95.0 < d["points"][-1]["value"] < 125.0
    test_client.delete(f"/api/index-history/custom/{cid}")


def test_custom_index_series_unknown_404(test_client):
    assert test_client.get("/api/index-history/custom/99999/series").status_code == 404
