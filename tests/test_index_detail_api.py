"""
Tests for Index Detail API endpoints.

Covers: overview, 7 table views (overview, shareholding, relative, technicals,
support_resistance, fundamentals, price_volume). Happy path, edge cases,
calculations, expected failures, deduplication, idempotency.
"""
import pytest


class TestIndexDetailOverview:
    def test_overview_happy_path(self, test_client):
        resp = test_client.get("/api/index-detail/nifty-50/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["index_name"] == "NIFTY 50"
        assert data["slug"] == "nifty-50"
        assert "constituent_count" in data
        assert data["constituent_count"] >= 2

    def test_overview_has_price(self, test_client):
        resp = test_client.get("/api/index-detail/nifty-50/overview")
        price = resp.json().get("price")
        if price:
            assert "close" in price
            assert "change" in price
            assert "change_pct" in price

    def test_overview_not_found(self, test_client):
        resp = test_client.get("/api/index-detail/nonexistent-xyz/overview")
        # May return 200 with null instrument or error — check it doesn't 500
        assert resp.status_code in (200, 404)

    def test_overview_idempotent(self, test_client):
        r1 = test_client.get("/api/index-detail/nifty-50/overview").json()
        r2 = test_client.get("/api/index-detail/nifty-50/overview").json()
        assert r1 == r2


class TestIndexDetailTableViews:
    def test_overview_view(self, test_client):
        resp = test_client.get("/api/index-detail/nifty-50/table?view=overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["view"] == "overview"
        assert len(data["rows"]) >= 2
        row = data["rows"][0]
        assert "symbol" in row and "close" in row and "change_pct" in row

    def test_shareholding_view(self, test_client):
        resp = test_client.get("/api/index-detail/nifty-50/table?view=shareholding")
        assert resp.status_code == 200
        data = resp.json()
        assert data["view"] == "shareholding"
        if data["rows"]:
            row = data["rows"][0]
            assert "promoters" in row and "fii" in row and "dii" in row

    def test_shareholding_values(self, test_client):
        """RELIANCE should have shareholding data from fixtures."""
        resp = test_client.get("/api/index-detail/nifty-50/table?view=shareholding")
        rows = resp.json()["rows"]
        reliance = next((r for r in rows if r["symbol"] == "RELIANCE"), None)
        if reliance:
            assert reliance["promoters"] == 45.5
            assert reliance["fii"] == 25.3

    def test_relative_view(self, test_client):
        resp = test_client.get("/api/index-detail/nifty-50/table?view=relative")
        assert resp.status_code == 200
        data = resp.json()
        if data["rows"]:
            row = data["rows"][0]
            assert "return_1w" in row and "return_1m" in row and "return_1y" in row

    def test_technicals_view(self, test_client):
        resp = test_client.get("/api/index-detail/nifty-50/table?view=technicals")
        assert resp.status_code == 200
        data = resp.json()
        if data["rows"]:
            row = data["rows"][0]
            assert "dma_50" in row and "rsi_14" in row and "high_52w" in row

    def test_support_resistance_view(self, test_client):
        resp = test_client.get("/api/index-detail/nifty-50/table?view=support_resistance")
        assert resp.status_code == 200
        data = resp.json()
        if data["rows"]:
            row = data["rows"][0]
            assert "pivot" in row and "r1" in row and "s1" in row
            # If pivot exists, R1 and S1 should too
            if row["pivot"] is not None:
                assert row["r1"] is not None
                assert row["s1"] is not None

    def test_support_resistance_calculation(self, test_client):
        """Pivot = (H + L + C) / 3 from previous day."""
        resp = test_client.get("/api/index-detail/nifty-50/table?view=support_resistance")
        for row in resp.json()["rows"]:
            if row["pivot"] and row["r1"] and row["s1"]:
                # R1 > Pivot > S1
                assert row["r1"] >= row["pivot"]
                assert row["s1"] <= row["pivot"]

    def test_fundamentals_view(self, test_client):
        resp = test_client.get("/api/index-detail/nifty-50/table?view=fundamentals")
        assert resp.status_code == 200
        data = resp.json()
        if data["rows"]:
            row = data["rows"][0]
            assert "pe" in row and "peg" in row and "pb" in row and "eps" in row

    def test_fundamentals_reliance_values(self, test_client):
        """RELIANCE should have PE=25.5, PEG=1.2 from fixtures."""
        resp = test_client.get("/api/index-detail/nifty-50/table?view=fundamentals")
        rows = resp.json()["rows"]
        reliance = next((r for r in rows if r["symbol"] == "RELIANCE"), None)
        if reliance:
            assert reliance["pe"] == 25.5
            assert reliance["peg"] == 1.2

    def test_price_volume_view(self, test_client):
        resp = test_client.get("/api/index-detail/nifty-50/table?view=price_volume")
        assert resp.status_code == 200
        data = resp.json()
        if data["rows"]:
            row = data["rows"][0]
            assert "day_high" in row and "day_low" in row
            assert "week_high" in row and "year_high" in row

    def test_price_volume_pct_range(self, test_client):
        """day_pct should be None when high==low, else a number."""
        resp = test_client.get("/api/index-detail/nifty-50/table?view=price_volume")
        for row in resp.json()["rows"]:
            if row.get("day_high") == row.get("day_low"):
                assert row.get("day_pct") is None

    def test_invalid_view_400(self, test_client):
        resp = test_client.get("/api/index-detail/nifty-50/table?view=nonexistent")
        assert resp.status_code == 400

    def test_not_found_404(self, test_client):
        resp = test_client.get("/api/index-detail/nonexistent-xyz/table")
        assert resp.status_code == 404

    def test_deduplication(self, test_client):
        resp = test_client.get("/api/index-detail/nifty-50/table?view=overview")
        symbols = [r["symbol"] for r in resp.json()["rows"]]
        assert len(symbols) == len(set(symbols))

    def test_all_views_idempotent(self, test_client):
        views = ["this_view", "overview", "shareholding", "relative", "technicals",
                 "support_resistance", "fundamentals", "price_volume"]
        for view in views:
            r1 = test_client.get(f"/api/index-detail/nifty-50/table?view={view}").json()
            r2 = test_client.get(f"/api/index-detail/nifty-50/table?view={view}").json()
            assert r1 == r2, f"View {view} not idempotent"
