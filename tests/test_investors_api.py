"""Tests for /api/investors/* — registry, change classification (incl. the
per-stock filing gate), drill-down, matrix, groups, missing companies.

Seed design is documented in conftest._seed_investor_data.
"""
from backend.api.investors import classify_change


class TestClassifyChange:
    def test_new(self):
        assert classify_change(None, 1.2) == "new"
        assert classify_change(0, 1.2) == "new"

    def test_exit(self):
        assert classify_change(2.0, None) == "exit"
        assert classify_change(2.0, 0) == "exit"

    def test_add_trim_threshold(self):
        assert classify_change(1.0, 1.5) == "add"
        assert classify_change(1.5, 1.0) == "trim"
        assert classify_change(1.0, 1.02) is None   # below threshold
        assert classify_change(None, None) is None


def test_list_counts_and_badges(test_client):
    d = test_client.get("/api/investors/list").json()
    by_name = {i["name"]: i for i in d["investors"]}
    assert d["quarters"][0] == "2026-06-30"
    alpha = by_name["Alpha Investor"]
    assert alpha["holdings_latest"] == 2                 # RISKCO + GHOSTCO
    assert alpha["changes_latest"] == {"new": 1, "exit": 0, "add": 1, "trim": 0}
    beta = by_name["Beta Fund"]
    # RISKCO exit is real (Alpha filed RISKCO in Jun); DARKCO is NOT an
    # exit (nobody filed DARKCO in Jun — filings pending).
    assert beta["changes_latest"]["exit"] == 1


def test_list_category_filter(test_client):
    d = test_client.get("/api/investors/list?category=fii").json()
    names = {i["name"] for i in d["investors"]}
    assert "Beta Fund" in names
    assert "Alpha Investor" not in names


def test_changes_kinds_and_filing_gate(test_client):
    d = test_client.get("/api/investors/changes").json()
    assert d["quarter"] == "2026-06-30"
    kinds = {(c["investor"], c["stock_name"]): c["kind"] for c in d["changes"]}
    assert kinds[("Alpha Investor", "Riskco")] == "add"
    assert kinds[("Alpha Investor", "Ghost Co")] == "new"
    assert kinds[("Beta Fund", "Riskco")] == "exit"
    # DARKCO must NOT appear — its Jun filing hasn't landed anywhere
    assert ("Beta Fund", "Dark Co") not in kinds


def test_changes_kind_filter_and_sector(test_client):
    d = test_client.get("/api/investors/changes?kind=exit").json()
    assert len(d["changes"]) == 1
    c = d["changes"][0]
    assert c["stock_name"] == "Riskco"
    assert c["sector"] == "Testing Sector"
    assert c["tracked"] is True


def test_investor_drilldown(test_client):
    lst = test_client.get("/api/investors/list").json()["investors"]
    alpha_id = next(i["id"] for i in lst if i["name"] == "Alpha Investor")
    d = test_client.get(f"/api/investors/{alpha_id}/holdings").json()
    assert d["investor"]["name"] == "Alpha Investor"
    stocks = {h["stock_name"]: h for h in d["holdings"]}
    assert stocks["Riskco"]["quarters"]["2026-06-30"] == 2.0
    assert stocks["Riskco"]["latest_change"] == "add"
    assert stocks["Ghost Co"]["latest_change"] == "new"
    assert stocks["Ghost Co"]["tracked"] is False


def test_investor_drilldown_404(test_client):
    assert test_client.get("/api/investors/99999/holdings").status_code == 404


def test_matrix_by_sector_alphabetical(test_client):
    d = test_client.get("/api/investors/matrix?by=sector&quarters_count=4").json()
    rows = {r["row"]: r for r in d["rows"]}
    assert "Testing Sector" in rows            # only tracked stocks get sectors
    cell = rows["Testing Sector"]["cells"]["2026-03-31"]
    names = [e["investor"] for e in cell]
    assert names == sorted(names, key=str.lower)   # alphabetical within cell
    assert {e["investor"] for e in cell} == {"Alpha Investor", "Beta Fund"}


def test_matrix_by_stock_includes_untracked(test_client):
    d = test_client.get("/api/investors/matrix?by=stock&quarters_count=4").json()
    rows = {r["row"] for r in d["rows"]}
    assert "Ghost Co" in rows                  # untracked visible in stock mode
    assert "Riskco" in rows


def test_matrix_min_pct(test_client):
    d = test_client.get("/api/investors/matrix?by=stock&min_pct=2.5").json()
    rows = {r["row"]: r for r in d["rows"]}
    # Only Beta's 3.0% GHOSTCO position clears 2.5%
    assert set(rows) == {"Ghost Co"}


def test_missing_companies(test_client):
    d = test_client.get("/api/investors/missing-companies").json()
    names = {m["stock_name"]: m for m in d["missing"]}
    assert "Ghost Co" in names and "Dark Co" in names
    assert "Riskco" not in names               # tracked → not missing
    assert names["Ghost Co"]["holders_latest"] == 2


def test_groups_crud_and_views(test_client):
    lst = test_client.get("/api/investors/list").json()["investors"]
    ids = [i["id"] for i in lst if i["name"] in ("Alpha Investor", "Beta Fund")]

    r = test_client.post("/api/investors/groups",
                         json={"name": "Test Cartel", "member_ids": ids})
    assert r.status_code == 200, r.text
    gid = r.json()["id"]

    # Duplicate name
    assert test_client.post("/api/investors/groups",
                            json={"name": "Test Cartel", "member_ids": ids}).status_code == 409

    # Consolidated: RISKCO pct summed across members (Mar: 1.5 + 2.0)
    d = test_client.get(f"/api/investors/groups/{gid}/holdings?mode=consolidated").json()
    stocks = {h["stock_name"]: h for h in d["holdings"]}
    assert stocks["Riskco"]["quarters"]["2026-03-31"] == 3.5
    assert set(stocks) == {"Riskco", "Ghost Co", "Dark Co"}

    # Overlap: only stocks with >= 2 members holding in the LATEST quarter.
    # Jun: RISKCO held by Alpha only (Beta exited); GHOSTCO by both? No —
    # Alpha 1.2 + Beta 3.0 → 2 members → overlap includes Ghost Co only.
    d = test_client.get(f"/api/investors/groups/{gid}/holdings?mode=overlap").json()
    assert {h["stock_name"] for h in d["holdings"]} == {"Ghost Co"}

    # Update + delete
    assert test_client.put(f"/api/investors/groups/{gid}",
                           json={"name": "Cartel v2", "member_ids": ids}).status_code == 200
    assert test_client.delete(f"/api/investors/groups/{gid}").status_code == 200
    assert test_client.delete(f"/api/investors/groups/{gid}").status_code == 404


def test_group_validation(test_client):
    assert test_client.post("/api/investors/groups",
                            json={"name": "X", "member_ids": [1]}).status_code == 400
    assert test_client.post("/api/investors/groups",
                            json={"name": "", "member_ids": [1, 2]}).status_code == 400


def test_co_invest_matrix(test_client):
    # Latest quarter (Jun): Alpha and Beta share only GHOSTCO → 1 common.
    # Default min_overlap=2 filters the pair out entirely.
    d = test_client.get("/api/investors/co-invest").json()
    assert d["pairs"] == []
    assert d["quarter"] == "2026-06-30"

    d = test_client.get("/api/investors/co-invest?min_overlap=1").json()
    assert len(d["pairs"]) == 1
    pair = d["pairs"][0]
    assert pair["count"] == 1 and pair["stocks"] == ["Ghost Co"]
    names = {i["name"] for i in d["investors"]}
    assert names == {"Alpha Investor", "Beta Fund"}
    assert all(i["partners"] == 1 for i in d["investors"])

    # Mar quarter: the only common disclosed stock is RISKCO.
    d = test_client.get(
        "/api/investors/co-invest?min_overlap=1&quarter=2026-03-31").json()
    assert d["pairs"][0]["stocks"] == ["Riskco"]

    # Category filter narrows to one investor → no pairs possible.
    d = test_client.get("/api/investors/co-invest?min_overlap=1&category=fii").json()
    assert d["pairs"] == [] and d["total_investors"] == 1
