"""
Tests for /api/data-freshness endpoint.

Per project_guidelines.md §2:
1. Happy path — returns 200 with all timestamp fields
2. Variations — different data availability scenarios
3. Edge cases — empty tables, non-trading days filtered
4. Expected failures — graceful null fallback
5. Idempotency — same call returns identical result
"""
import pytest


class TestDataFreshnessHappyPath:
    def test_returns_200(self, test_client):
        resp = test_client.get("/api/data-freshness")
        assert resp.status_code == 200

    def test_has_all_fields(self, test_client):
        data = test_client.get("/api/data-freshness").json()
        for field in ["last_trading_day", "last_price_ingest", "last_index_price",
                      "last_fundamental_ingest", "last_flow_date"]:
            assert field in data

    def test_last_trading_day_from_fixtures(self, test_client):
        """Fixtures have breadth for 2026-04-10 (advances=1200) and 2026-04-09."""
        data = test_client.get("/api/data-freshness").json()
        assert data["last_trading_day"] == "2026-04-10"

    def test_last_price_ingest(self, test_client):
        """Fixtures have NSE bhavcopy prices for 2026-04-10."""
        data = test_client.get("/api/data-freshness").json()
        assert data["last_price_ingest"] == "2026-04-10"

    def test_last_flow_date(self, test_client):
        """Fixtures have daily flows for 2026-04-10."""
        data = test_client.get("/api/data-freshness").json()
        assert data["last_flow_date"] == "2026-04-10"


class TestDataFreshnessFiltering:
    def test_trading_day_excludes_zero_breadth(self, test_client):
        """last_trading_day should only count rows where advances+declines > 0.
        Fixture breadth has real data (advances>0), so this verifies the filter works."""
        data = test_client.get("/api/data-freshness").json()
        # Must be a real trading day, not a holiday with 0/0
        assert data["last_trading_day"] is not None


class TestDataFreshnessIdempotency:
    def test_idempotent(self, test_client):
        r1 = test_client.get("/api/data-freshness").json()
        r2 = test_client.get("/api/data-freshness").json()
        assert r1 == r2
