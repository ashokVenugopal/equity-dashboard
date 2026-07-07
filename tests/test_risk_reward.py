"""
Tests for the risk/reward computations (backend/core/risk_reward.py) and
the /api/company/{symbol}/risk-reward endpoint.

Pure-function tests carry the correctness burden (TTM rollups, altitude,
attribution decomposition, staleness guards); the endpoint test verifies
wiring against the seeded conftest DB (constant TTM EPS 40, prices ramping
800→1000 with current 900 → PE floor 20 / peak 25 / current 22.5).
"""
import math
from datetime import date, timedelta

import pytest

from backend.core.risk_reward import (
    build_attribution_rows,
    build_ttm_series,
    close_on_or_before,
    daily_ratio_series,
    decompose_price_change,
    gauge_from_series,
    value_as_of,
)


# ─────────────────────────────────────────────────────────── build_ttm_series

class TestBuildTtmSeries:
    def test_rolling_four_quarter_sums(self):
        q = [("2025-03-31", 1.0), ("2025-06-30", 2.0),
             ("2025-09-30", 3.0), ("2025-12-31", 4.0),
             ("2026-03-31", 5.0)]
        out = build_ttm_series(q)
        assert out == [("2025-12-31", 10.0), ("2026-03-31", 14.0)]

    def test_fewer_than_four_quarters_empty(self):
        assert build_ttm_series([("2025-03-31", 1.0), ("2025-06-30", 2.0)]) == []

    def test_unsorted_input_and_duplicates(self):
        q = [("2025-12-31", 4.0), ("2025-03-31", 1.0),
             ("2025-09-30", 3.0), ("2025-06-30", 2.0),
             ("2025-12-31", 40.0)]  # duplicate date — last wins
        out = build_ttm_series(q)
        assert out == [("2025-12-31", 46.0)]

    def test_none_values_dropped(self):
        q = [("2025-03-31", 1.0), ("2025-06-30", None),
             ("2025-09-30", 3.0), ("2025-12-31", 4.0)]
        assert build_ttm_series(q) == []  # only 3 usable quarters


# ─────────────────────────────────────────────────────────────── value_as_of

class TestValueAsOf:
    SERIES = [("2025-03-31", 10.0), ("2025-12-31", 20.0)]

    def test_between_points_takes_earlier(self):
        assert value_as_of(self.SERIES, "2025-06-15") == 10.0

    def test_exact_date(self):
        assert value_as_of(self.SERIES, "2025-12-31") == 20.0

    def test_before_all_none(self):
        assert value_as_of(self.SERIES, "2024-01-01") is None

    def test_after_all_takes_latest(self):
        assert value_as_of(self.SERIES, "2026-06-01") == 20.0

    def test_empty(self):
        assert value_as_of([], "2025-01-01") is None


# ───────────────────────────────────────────────────────── daily_ratio_series

class TestDailyRatioSeries:
    def test_pe_style_ratio(self):
        prices = [("2025-06-01", 100.0), ("2025-06-02", 110.0)]
        eps = [("2025-03-31", 10.0)]
        assert daily_ratio_series(prices, eps) == [
            ("2025-06-01", 10.0), ("2025-06-02", 11.0)]

    def test_days_before_denominator_skipped(self):
        prices = [("2025-01-01", 100.0), ("2025-06-01", 100.0)]
        eps = [("2025-03-31", 10.0)]
        assert daily_ratio_series(prices, eps) == [("2025-06-01", 10.0)]

    def test_negative_denominator_skipped(self):
        """Negative TTM EPS → PE meaningless; day dropped, not plotted."""
        prices = [("2025-06-01", 100.0)]
        eps = [("2025-03-31", -5.0)]
        assert daily_ratio_series(prices, eps) == []

    def test_ev_style_extra_and_multiplier(self):
        # EV = close × 2 + 50; EBITDA = 10 → (100·2 + 50)/10 = 25
        prices = [("2025-06-01", 100.0)]
        ebitda = [("2025-03-31", 10.0)]
        out = daily_ratio_series(prices, ebitda,
                                 numerator_extra=50.0, price_multiplier=2.0)
        assert out == [("2025-06-01", 25.0)]


# ───────────────────────────────────────────────────────── gauge_from_series

class TestGaugeFromSeries:
    def test_basic_altitude(self):
        s = [("2025-01-01", 20.0), ("2025-06-01", 30.0), ("2025-12-31", 22.5)]
        g = gauge_from_series(s)
        assert g["floor"] == 20.0 and g["peak"] == 30.0
        assert g["current"] == 22.5
        assert g["altitude_pct"] == 25.0
        assert g["current_date"] == "2025-12-31"

    def test_flat_series_altitude_half(self):
        g = gauge_from_series([("2025-01-01", 5.0), ("2025-02-01", 5.0)])
        assert g["altitude_pct"] == 50.0

    def test_empty_returns_none(self):
        assert gauge_from_series([]) is None

    def test_trend_downsampled_and_ends_at_current(self):
        s = [(f"2025-01-{i+1:02d}", float(i)) for i in range(28)]
        s += [(f"2025-02-{i+1:02d}", float(28+i)) for i in range(28)]
        s += [(f"2025-03-{i+1:02d}", float(56+i)) for i in range(28)]
        g = gauge_from_series(s, max_trend_points=20)
        assert len(g["trend"]) <= 21
        assert g["trend"][-1]["date"] == s[-1][0]

    def test_current_at_peak_is_100(self):
        g = gauge_from_series([("2025-01-01", 10.0), ("2025-02-01", 40.0)])
        assert g["altitude_pct"] == 100.0


# ─────────────────────────────────────────────────── decompose_price_change

class TestDecomposePriceChange:
    def test_pure_multiple_move(self):
        """Price doubles, earnings flat → 100% multiple-driven."""
        d = decompose_price_change(100.0, 200.0, 10.0, 10.0)
        assert d["price_change_pct"] == 100.0
        assert d["earnings_change_pct"] == 0.0
        assert d["multiple_change_pct"] == 100.0
        assert d["earnings_share_pct"] == 0.0
        assert d["multiple_share_pct"] == 100.0

    def test_pure_earnings_move(self):
        d = decompose_price_change(100.0, 200.0, 10.0, 20.0)
        assert d["earnings_share_pct"] == 100.0
        assert d["multiple_share_pct"] == 0.0

    def test_mixed_move_shares_sum_to_100(self):
        d = decompose_price_change(100.0, 180.0, 10.0, 13.0)
        assert d["earnings_share_pct"] + d["multiple_share_pct"] == pytest.approx(100.0)
        # earnings grew 30%, price 80% → earnings share = ln(1.3)/ln(1.8)
        expected = math.log(1.3) / math.log(1.8) * 100
        assert d["earnings_share_pct"] == pytest.approx(expected, abs=0.11)

    def test_negative_eps_gives_price_only(self):
        """Loss-making at either end → change %s but no attribution."""
        d = decompose_price_change(100.0, 150.0, -5.0, 10.0)
        assert d["price_change_pct"] == 50.0
        assert d["earnings_change_pct"] is None
        assert d["earnings_share_pct"] is None

    def test_missing_prices_none(self):
        assert decompose_price_change(None, 100.0, 10.0, 10.0) is None
        assert decompose_price_change(100.0, None, 10.0, 10.0) is None
        assert decompose_price_change(0.0, 100.0, 10.0, 10.0) is None

    def test_zero_price_move_no_share_split(self):
        """~0% price move → log shares would explode; split omitted."""
        d = decompose_price_change(100.0, 100.0, 10.0, 12.0)
        assert d["price_change_pct"] == 0.0
        assert d["earnings_share_pct"] is None


# ───────────────────────────────────────────────────────── close_on_or_before

class TestCloseOnOrBefore:
    PRICES = [("2025-01-01", 100.0), ("2025-06-01", 110.0)]

    def test_nearest_earlier(self):
        assert close_on_or_before(self.PRICES, "2025-03-01") == 100.0

    def test_staleness_guard_rejects_gap(self):
        """A close 59 days before the boundary fails a 30-day tolerance —
        guards against multi-month price-history gaps."""
        assert close_on_or_before(self.PRICES, "2025-03-01",
                                  max_staleness_days=30) is None

    def test_staleness_guard_accepts_within_tolerance(self):
        assert close_on_or_before(self.PRICES, "2025-01-15",
                                  max_staleness_days=30) == 100.0


# ────────────────────────────────────────────────────── build_attribution_rows

def _daily_prices(start: date, days: int, price_fn) -> list:
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        if d.weekday() < 5:
            out.append((d.isoformat(), price_fn(i)))
    return out


class TestBuildAttributionRows:
    def test_all_windows_with_flat_earnings(self):
        start = date(2023, 1, 2)
        prices = _daily_prices(start, 1250, lambda i: 100.0 + i * 0.1)
        # Constant TTM EPS covering the whole span
        ttm = [("2022-12-31", 10.0)]
        rows = build_attribution_rows(prices, ttm)
        by_window = {r["window"]: r for r in rows}
        assert set(by_window) == {"1W", "1M", "3M", "6M", "1Y", "3Y"}
        for r in rows:
            assert r["available"] is True
            assert r["earnings_change_pct"] == 0.0

    def test_gap_in_price_history_marks_unavailable(self):
        """6M boundary falls inside a long gap → row unavailable, never a
        months-stale baseline."""
        recent_start = date(2026, 3, 1)
        prices = [("2022-08-01", 50.0)]  # ancient row, then a gap
        prices += _daily_prices(recent_start, 120, lambda i: 100.0)
        rows = build_attribution_rows(prices, [("2022-01-01", 10.0)])
        by_window = {r["window"]: r for r in rows}
        assert by_window["1M"]["available"] is True
        assert by_window["1Y"]["available"] is False
        assert by_window["3Y"]["available"] is False

    def test_annual_fallback_when_ttm_too_short(self):
        """3Y boundary predates the TTM series → annual EPS used."""
        start = date(2023, 1, 2)
        prices = _daily_prices(start, 1250, lambda i: 100.0)
        ttm = [("2025-06-30", 12.0)]                # starts too late for 3Y
        annual = [("2022-03-31", 8.0), ("2025-03-31", 12.0)]
        rows = build_attribution_rows(prices, ttm, annual)
        by_window = {r["window"]: r for r in rows}
        assert by_window["3Y"]["available"] is True
        assert by_window["3Y"]["eps_source"] == "annual"
        assert by_window["1W"]["eps_source"] == "ttm"

    def test_empty_prices(self):
        assert build_attribution_rows([], [("2025-01-01", 1.0)]) == []


# ──────────────────────────────────────────────────────────────── endpoint

class TestRiskRewardEndpoint:
    def test_endpoint_shape_and_pe_gauge(self, test_client):
        resp = test_client.get("/api/company/RISKCO/risk-reward")
        assert resp.status_code == 200
        d = resp.json()
        assert d["symbol"] == "RISKCO"

        # Seeded: TTM EPS 40 constant; prices ramp 800→1000, current 900.
        pe = d["pe"]
        assert pe is not None
        # prices[-252:] trims the earliest few rows of the ramp, so the
        # floor sits slightly above the theoretical 20.0
        assert 20.0 <= pe["floor"] <= 21.0
        assert pe["peak"] == pytest.approx(25.0, abs=0.2)
        assert pe["current"] == pytest.approx(22.5, abs=0.1)
        assert 40.0 <= pe["altitude_pct"] <= 60.0
        assert len(pe["trend"]) >= 10
        assert pe["trend"][-1]["date"] == pe["current_date"]

    def test_endpoint_ocf_pat_gauge(self, test_client):
        d = test_client.get("/api/company/RISKCO/risk-reward").json()
        ocf = d["ocf_pat"]
        assert ocf is not None
        # Seeded ratios 0.5 / 1.0 / 0.8 (+ the conftest's pre-existing
        # 2025-03-31 annual net_profit has no matching cfo → excluded)
        assert ocf["floor"] == pytest.approx(0.5)
        assert ocf["peak"] == pytest.approx(1.0)
        assert ocf["current"] == pytest.approx(0.8)
        assert ocf["altitude_pct"] == pytest.approx(60.0)

    def test_endpoint_attribution_flat_earnings(self, test_client):
        d = test_client.get("/api/company/RISKCO/risk-reward").json()
        rows = {r["window"]: r for r in d["attribution"]}
        assert set(rows) == {"1W", "1M", "3M", "6M", "1Y", "3Y"}
        # Constant TTM EPS → any available window is 100% multiple-driven
        for w in ("1M", "3M", "6M"):
            if rows[w]["available"]:
                assert rows[w]["earnings_change_pct"] == 0.0
                assert rows[w]["multiple_share_pct"] in (None, 100.0)
        # 3Y predates seeded history → unavailable
        assert rows["3Y"]["available"] is False

    def test_endpoint_ev_gauge_absent_without_inputs(self, test_client):
        """No num_equity_shares seeded → EV/EBITDA gauge omitted, not 500."""
        d = test_client.get("/api/company/RISKCO/risk-reward").json()
        assert d["ev_ebitda"] is None

    def test_endpoint_company_not_found(self, test_client):
        assert test_client.get("/api/company/NOPE/risk-reward").status_code == 404

    def test_endpoint_company_with_no_fundamentals(self, test_client):
        """TCS has an instrument but no quarterly EPS/cash-flow seeds —
        endpoint must degrade to null gauges or 404 (no prices), never 500."""
        resp = test_client.get("/api/company/TCS/risk-reward")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            d = resp.json()
            assert d["pe"] is None
            assert d["ev_ebitda"] is None
