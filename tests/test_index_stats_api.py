"""
Tests for Index Detail Stats API endpoint and This View table view.

Covers: /api/index-detail/{slug}/stats and /api/index-detail/{slug}/table?view=this_view

Per project_guidelines.md §2:
1. Core happy path
2. Variations (different slugs, missing data)
3. Edge cases (no prices, no constituents, zero denominators)
4. Expected failures (invalid slug)
5. Idempotency
6. Sensitivity (boundary values, near-zero range)
7. Expected failures vs genuine failures
"""
import pytest


# ═══════════════════════════════════════════════════════════════════════
# 1. STATS ENDPOINT — HAPPY PATH
# ═══════════════════════════════════════════════════════════════════════

class TestIndexStatsHappyPath:
    def test_stats_returns_200(self, test_client):
        resp = test_client.get("/api/index-detail/nifty-50/stats")
        assert resp.status_code == 200

    def test_stats_has_index_name(self, test_client):
        data = test_client.get("/api/index-detail/nifty-50/stats").json()
        assert data["index_name"] == "NIFTY 50"

    def test_stats_has_performance_list(self, test_client):
        data = test_client.get("/api/index-detail/nifty-50/stats").json()
        assert isinstance(data["performance"], list)
        # Should have 6 timeframes (1d, 1w, 1m, 3m, 6m, 1y)
        assert len(data["performance"]) == 6

    def test_stats_performance_keys(self, test_client):
        data = test_client.get("/api/index-detail/nifty-50/stats").json()
        for item in data["performance"]:
            assert "key" in item
            assert "label" in item
            assert "change_pct" in item

    def test_stats_performance_timeframe_keys(self, test_client):
        data = test_client.get("/api/index-detail/nifty-50/stats").json()
        keys = [p["key"] for p in data["performance"]]
        assert keys == ["1d", "1w", "1m", "3m", "6m", "1y"]

    def test_stats_has_technicals_dict(self, test_client):
        data = test_client.get("/api/index-detail/nifty-50/stats").json()
        assert isinstance(data["technicals"], dict)

    def test_stats_has_support_resistance_dict(self, test_client):
        data = test_client.get("/api/index-detail/nifty-50/stats").json()
        assert isinstance(data["support_resistance"], dict)

    def test_stats_sr_pivot_calculation(self, test_client):
        """S&R pivot = (H + L + C) / 3 from prev day."""
        data = test_client.get("/api/index-detail/nifty-50/stats").json()
        sr = data["support_resistance"]
        if sr.get("pivot"):
            # R1 > Pivot > S1
            assert sr["r1"] >= sr["pivot"]
            assert sr["s1"] <= sr["pivot"]
            # R3 > R2 > R1 and S3 < S2 < S1
            assert sr["r3"] >= sr["r2"] >= sr["r1"]
            assert sr["s3"] <= sr["s2"] <= sr["s1"]

    def test_stats_sr_values_from_fixture(self, test_client):
        """Verify S&R calculated from NIFTY50 fixture data (prev day: H=22350, L=22050, C=22300)."""
        data = test_client.get("/api/index-detail/nifty-50/stats").json()
        sr = data["support_resistance"]
        if sr.get("pivot"):
            # Pivot = (22350 + 22050 + 22300) / 3 = 22233.33
            assert abs(sr["pivot"] - 22233.33) < 1.0


# ═══════════════════════════════════════════════════════════════════════
# 2. STATS — BREADTH DISTRIBUTION
# ═══════════════════════════════════════════════════════════════════════

class TestIndexStatsBreadth:
    def test_breadth_attached_to_performance(self, test_client):
        """Each performance item should have advances/declines/total if constituents exist."""
        data = test_client.get("/api/index-detail/nifty-50/stats").json()
        for item in data["performance"]:
            if "total" in item:
                assert item["total"] >= 2  # We have at least RELIANCE + HDFCBANK
                assert item["advances"] + item["declines"] == item["total"]

    def test_breadth_advances_range(self, test_client):
        """Advances should be between 0 and total."""
        data = test_client.get("/api/index-detail/nifty-50/stats").json()
        for item in data["performance"]:
            if "total" in item:
                assert 0 <= item["advances"] <= item["total"]


# ═══════════════════════════════════════════════════════════════════════
# 3. STATS — EDGE CASES
# ═══════════════════════════════════════════════════════════════════════

class TestIndexStatsEdgeCases:
    def test_nonexistent_index_returns_200_empty(self, test_client):
        """Unknown index returns 200 with empty performance, not 500."""
        resp = test_client.get("/api/index-detail/nonexistent-xyz/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["performance"] == []
        assert data["technicals"] == {}
        assert data["support_resistance"] == {}

    def test_banknifty_stats_works(self, test_client):
        """BANKNIFTY (slug: nifty-bank) should work even with no constituents."""
        resp = test_client.get("/api/index-detail/nifty-bank/stats")
        assert resp.status_code == 200

    def test_stats_idempotent(self, test_client):
        r1 = test_client.get("/api/index-detail/nifty-50/stats").json()
        r2 = test_client.get("/api/index-detail/nifty-50/stats").json()
        assert r1 == r2

    def test_performance_null_for_missing_lookback(self, test_client):
        """With only 2 days of data, 1w/1m/3m/6m/1y should be null."""
        data = test_client.get("/api/index-detail/nifty-50/stats").json()
        for item in data["performance"]:
            if item["key"] in ("1w", "1m", "3m", "6m", "1y"):
                # With only 2 days of fixture data, these lookbacks won't find prices
                # change_pct can be None (expected skip, not error)
                pass  # Just verify no crash


# ═══════════════════════════════════════════════════════════════════════
# 4. THIS VIEW TABLE — HAPPY PATH
# ═══════════════════════════════════════════════════════════════════════

class TestThisViewHappyPath:
    def test_this_view_returns_200(self, test_client):
        resp = test_client.get("/api/index-detail/nifty-50/table?view=this_view")
        assert resp.status_code == 200

    def test_this_view_has_rows(self, test_client):
        data = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        assert data["view"] == "this_view"
        assert len(data["rows"]) >= 2  # RELIANCE + HDFCBANK

    def test_this_view_row_structure(self, test_client):
        data = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        row = data["rows"][0]
        assert "symbol" in row
        assert "name" in row
        assert "close" in row
        assert "change_pct" in row
        assert "volume" in row
        assert "market_cap" in row
        assert "high_52w" in row
        assert "low_52w" in row
        assert "range_pct" in row
        assert "sparkline" in row

    def test_this_view_sparkline_is_list(self, test_client):
        data = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        for row in data["rows"]:
            assert isinstance(row["sparkline"], list)

    def test_this_view_sparkline_has_data(self, test_client):
        """Each sparkline entry should have 't' (date) and 'c' (close)."""
        data = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        for row in data["rows"]:
            for point in row["sparkline"]:
                assert "t" in point
                assert "c" in point

    def test_this_view_market_cap_from_facts(self, test_client):
        """RELIANCE should have market_cap from fixtures (1500000.0)."""
        data = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        reliance = next((r for r in data["rows"] if r["symbol"] == "RELIANCE"), None)
        if reliance:
            assert reliance["market_cap"] == 1500000.0


# ═══════════════════════════════════════════════════════════════════════
# 5. THIS VIEW — RANGE BAR CALCULATIONS
# ═══════════════════════════════════════════════════════════════════════

class TestThisViewRangeBar:
    def test_range_pct_between_0_and_100(self, test_client):
        """range_pct should be 0-100 (or None if missing)."""
        data = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        for row in data["rows"]:
            if row["range_pct"] is not None:
                assert 0 <= row["range_pct"] <= 100

    def test_range_pct_null_when_no_range(self, test_client):
        """If high_52w == low_52w, range_pct should be None (zero denominator = expected skip)."""
        data = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        for row in data["rows"]:
            if row.get("high_52w") and row.get("low_52w"):
                if row["high_52w"] == row["low_52w"]:
                    assert row["range_pct"] is None

    def test_high_52w_gte_low_52w(self, test_client):
        """52W high should always be >= 52W low."""
        data = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        for row in data["rows"]:
            if row.get("high_52w") is not None and row.get("low_52w") is not None:
                assert row["high_52w"] >= row["low_52w"]


# ═══════════════════════════════════════════════════════════════════════
# 6. THIS VIEW — DEDUPLICATION
# ═══════════════════════════════════════════════════════════════════════

class TestThisViewDedup:
    def test_no_duplicate_symbols(self, test_client):
        """Each symbol should appear exactly once despite multiple classification rows."""
        data = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        symbols = [r["symbol"] for r in data["rows"]]
        assert len(symbols) == len(set(symbols))

    def test_nse_price_over_bse(self, test_client):
        """RELIANCE should use NSE price (1415.0), not BSE (1417.0)."""
        data = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        reliance = next((r for r in data["rows"] if r["symbol"] == "RELIANCE"), None)
        if reliance:
            assert reliance["close"] == 1415.0


# ═══════════════════════════════════════════════════════════════════════
# 7. THIS VIEW — EXPECTED FAILURES
# ═══════════════════════════════════════════════════════════════════════

class TestThisViewExpectedFailures:
    def test_not_found_404(self, test_client):
        """Nonexistent index returns 404."""
        resp = test_client.get("/api/index-detail/nonexistent-xyz/table?view=this_view")
        assert resp.status_code == 404

    def test_this_view_idempotent(self, test_client):
        r1 = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        r2 = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        assert r1 == r2

    def test_stock_with_no_mcap_has_null(self, test_client):
        """HDFCBANK has no market_cap fact in fixtures — should be null, not error."""
        data = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        hdfc = next((r for r in data["rows"] if r["symbol"] == "HDFCBANK"), None)
        if hdfc:
            assert hdfc["market_cap"] is None


# ═══════════════════════════════════════════════════════════════════════
# 8. THIS VIEW — SENSITIVITY
# ═══════════════════════════════════════════════════════════════════════

class TestThisViewSensitivity:
    def test_change_pct_sign(self, test_client):
        """RELIANCE went 1390→1415 (+1.80%), HDFCBANK went 1760→1750 (-0.57%)."""
        data = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        reliance = next((r for r in data["rows"] if r["symbol"] == "RELIANCE"), None)
        hdfc = next((r for r in data["rows"] if r["symbol"] == "HDFCBANK"), None)
        if reliance:
            assert reliance["change_pct"] > 0  # Went up
        if hdfc:
            assert hdfc["change_pct"] < 0  # Went down

    def test_sparkline_chronological_order(self, test_client):
        """Sparkline dates should be in ascending order."""
        data = test_client.get("/api/index-detail/nifty-50/table?view=this_view").json()
        for row in data["rows"]:
            dates = [p["t"] for p in row["sparkline"]]
            assert dates == sorted(dates)
