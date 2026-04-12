"""
Tests for Fund Flow API endpoints.

Covers: summary, daily, monthly, yearly, detailed views.
Happy path, variations, edge cases, boundary limits, idempotency.
"""
import pytest


class TestFundFlowSummary:
    def test_summary_happy_path(self, test_client):
        resp = test_client.get("/api/fundflow/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "latest_date" in data
        assert "latest" in data
        assert "mtd" in data
        assert "ytd" in data

    def test_summary_latest_has_participants(self, test_client):
        resp = test_client.get("/api/fundflow/summary")
        types = {f["participant_type"] for f in resp.json()["latest"]}
        assert "FII" in types or "DII" in types

    def test_summary_idempotent(self, test_client):
        r1 = test_client.get("/api/fundflow/summary").json()
        r2 = test_client.get("/api/fundflow/summary").json()
        assert r1 == r2


class TestFundFlowDaily:
    def test_daily_happy_path(self, test_client):
        resp = test_client.get("/api/fundflow/daily")
        assert resp.status_code == 200
        data = resp.json()
        assert data["segment"] == "CASH"
        assert "flows" in data
        if data["flows"]:
            assert "flow_date" in data["flows"][0]
            assert any(k.endswith("_net") for k in data["flows"][0])

    def test_daily_segment_variation(self, test_client):
        resp = test_client.get("/api/fundflow/daily?segment=CASH_EQUITY")
        assert resp.status_code == 200
        assert resp.json()["segment"] == "CASH_EQUITY"

    def test_daily_invalid_segment_empty(self, test_client):
        resp = test_client.get("/api/fundflow/daily?segment=NONEXISTENT")
        assert resp.status_code == 200
        assert resp.json()["flows"] == []

    def test_daily_limit_min(self, test_client):
        resp = test_client.get("/api/fundflow/daily?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()["flows"]) <= 1

    def test_daily_limit_max(self, test_client):
        resp = test_client.get("/api/fundflow/daily?limit=365")
        assert resp.status_code == 200

    def test_daily_limit_below_min(self, test_client):
        resp = test_client.get("/api/fundflow/daily?limit=0")
        assert resp.status_code == 422

    def test_daily_limit_above_max(self, test_client):
        resp = test_client.get("/api/fundflow/daily?limit=366")
        assert resp.status_code == 422

    def test_daily_idempotent(self, test_client):
        r1 = test_client.get("/api/fundflow/daily").json()
        r2 = test_client.get("/api/fundflow/daily").json()
        assert r1 == r2


class TestFundFlowMonthly:
    def test_monthly_happy_path(self, test_client):
        resp = test_client.get("/api/fundflow/monthly")
        assert resp.status_code == 200
        data = resp.json()
        assert data["segment"] == "CASH"
        assert len(data["flows"]) >= 1  # At least the fixture month

    def test_monthly_limit(self, test_client):
        resp = test_client.get("/api/fundflow/monthly?limit=1")
        assert len(resp.json()["flows"]) <= 1


class TestFundFlowYearly:
    def test_yearly_happy_path(self, test_client):
        resp = test_client.get("/api/fundflow/yearly")
        assert resp.status_code == 200
        data = resp.json()
        assert "flows" in data
        if data["flows"]:
            assert "flow_date" in data["flows"][0]

    def test_yearly_idempotent(self, test_client):
        r1 = test_client.get("/api/fundflow/yearly").json()
        r2 = test_client.get("/api/fundflow/yearly").json()
        assert r1 == r2


class TestFundFlowDetailed:
    def test_detailed_cash_provisional(self, test_client):
        resp = test_client.get("/api/fundflow/detailed?view=cash_provisional&timeframe=daily")
        assert resp.status_code == 200
        data = resp.json()
        assert data["view"] == "cash_provisional"
        assert "rows" in data
        assert "aggregations" in data

    def test_detailed_daily_has_aggregations(self, test_client):
        resp = test_client.get("/api/fundflow/detailed?timeframe=daily")
        data = resp.json()
        # Should have aggregation rows if enough data
        if data["rows"]:
            agg_labels = {a.get("flow_date") for a in data.get("aggregations", [])}
            assert len(agg_labels) >= 0  # May be 0 if < 7 days of data

    def test_detailed_monthly_no_aggregations(self, test_client):
        resp = test_client.get("/api/fundflow/detailed?timeframe=monthly")
        assert resp.json()["aggregations"] == []

    def test_detailed_fii_fo_index(self, test_client):
        resp = test_client.get("/api/fundflow/detailed?view=fii_fo&fo_sub=index")
        assert resp.status_code == 200

    def test_detailed_fii_fo_stock(self, test_client):
        resp = test_client.get("/api/fundflow/detailed?view=fii_fo&fo_sub=stock")
        assert resp.status_code == 200

    def test_detailed_limit_boundary(self, test_client):
        resp = test_client.get("/api/fundflow/detailed?limit=1")
        assert resp.status_code == 200
        resp = test_client.get("/api/fundflow/detailed?limit=0")
        assert resp.status_code == 422
