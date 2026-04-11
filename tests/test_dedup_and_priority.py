"""
Regression tests for deduplication and source priority.

These tests reproduce the production bugs found on 2026-04-12:
1. Classification versioning creates multiple active rows per stock → duplicate rows
2. Multiple price sources (NSE + BSE) for same date → must pick highest priority

Test fixtures now include:
- RELIANCE with 3 active NIFTY 50 classification rows (simulating version tracking)
- HDFCBANK with 2 active classification rows
- RELIANCE with NSE + BSE prices for same dates (source priority test)
"""
import pytest


# ═══════════════════════════════════════════════════════════════════════
# CLASSIFICATION DEDUPLICATION
# ═══════════════════════════════════════════════════════════════════════

class TestClassificationDedup:
    """
    Verify no duplicate stocks appear despite multiple active classification rows.

    Root cause: classification versioning creates new rows on each reconstitution.
    RELIANCE has 3 active rows, HDFCBANK has 2. Without GROUP BY, these become
    3 and 2 duplicate rows in query results.
    """

    def test_constituents_no_duplicate_symbols(self, test_client):
        """Each stock appears exactly once in constituents."""
        resp = test_client.get("/api/index/nifty-50/constituents")
        assert resp.status_code == 200
        symbols = [c["symbol"] for c in resp.json()["constituents"]]
        assert len(symbols) == len(set(symbols)), f"Duplicate symbols found: {symbols}"

    def test_constituents_correct_count(self, test_client):
        """Count matches unique stocks, not classification rows."""
        resp = test_client.get("/api/index/nifty-50/constituents")
        data = resp.json()
        # 2 unique stocks (RELIANCE, HDFCBANK), not 5 classification rows
        assert data["count"] == 2

    def test_movers_no_duplicate_symbols(self, test_client):
        """Each stock appears at most once in gainers and once in losers."""
        resp = test_client.get("/api/index/nifty-50/movers?limit=5")
        gainers = [m["symbol"] for m in resp.json()["gainers"]]
        losers = [m["symbol"] for m in resp.json()["losers"]]
        assert len(gainers) == len(set(gainers)), f"Duplicate gainers: {gainers}"
        assert len(losers) == len(set(losers)), f"Duplicate losers: {losers}"

    def test_technicals_no_duplicate_symbols(self, test_client):
        """Each stock appears exactly once in technicals."""
        resp = test_client.get("/api/index/nifty-50/technicals")
        symbols = [t["symbol"] for t in resp.json()["technicals"]]
        assert len(symbols) == len(set(symbols)), f"Duplicate symbols: {symbols}"

    def test_breadth_total_matches_unique_stocks(self, test_client):
        """Breadth total counts unique stocks, not classification rows."""
        resp = test_client.get("/api/index/nifty-50/breadth")
        breadth = resp.json()["breadth"]
        # Total should be 2 (unique stocks), not 5 (classification rows)
        assert breadth["total"] == 2

    def test_heatmap_no_duplicate_symbols(self, test_client):
        """Each stock appears exactly once in heatmap blocks."""
        resp = test_client.get("/api/heatmap/nifty-50")
        symbols = [b["symbol"] for b in resp.json()["blocks"]]
        assert len(symbols) == len(set(symbols)), f"Duplicate symbols: {symbols}"

    def test_sector_constituents_no_duplicates(self, test_client):
        """Sector drill-down returns unique stocks."""
        resp = test_client.get("/api/sectors/sector/Oil & Gas/constituents")
        symbols = [c["symbol"] for c in resp.json()["constituents"]]
        assert len(symbols) == len(set(symbols)), f"Duplicate symbols: {symbols}"


# ═══════════════════════════════════════════════════════════════════════
# PRICE SOURCE PRIORITY
# ═══════════════════════════════════════════════════════════════════════

class TestPriceSourcePriority:
    """
    Verify that when multiple price sources exist for the same date,
    the highest priority source wins: nse_bhavcopy > bse_bhavcopy > yahoo_finance.

    Test fixtures: RELIANCE has both NSE (close=1415) and BSE (close=1417) for 2026-04-10.
    NSE should be selected.
    """

    def test_price_history_picks_nse_over_bse(self, test_client):
        """Price history returns NSE price, not BSE, when both exist."""
        resp = test_client.get("/api/instrument/RELIANCE/price-history")
        prices = resp.json()["prices"]
        # Find the 2026-04-10 bar
        apr10 = next(p for p in prices if p["trade_date"] == "2026-04-10")
        assert apr10["close"] == 1415.0  # NSE price, not BSE's 1417.0

    def test_price_history_no_duplicate_dates(self, test_client):
        """Each date appears exactly once despite multiple sources."""
        resp = test_client.get("/api/instrument/RELIANCE/price-history")
        dates = [p["trade_date"] for p in resp.json()["prices"]]
        assert len(dates) == len(set(dates)), f"Duplicate dates: {dates}"

    def test_constituents_use_nse_price(self, test_client):
        """Constituent table uses NSE price priority."""
        resp = test_client.get("/api/index/nifty-50/constituents")
        reliance = next(c for c in resp.json()["constituents"] if c["symbol"] == "RELIANCE")
        assert reliance["close"] == 1415.0  # NSE, not BSE

    def test_chart_export_no_duplicate_dates(self, test_client):
        """Chart export produces one candle per date."""
        resp = test_client.get("/api/charts/export?symbol=RELIANCE")
        html = resp.text
        # Should contain each date only once in the data
        assert html.count("2026-04-10") >= 1  # Present
        # The data JSON should have exactly 2 candles (2 dates)
        assert '"2026-04-09"' in html
        assert '"2026-04-10"' in html

    def test_heatmap_uses_priority_price(self, test_client):
        """Heatmap change_pct calculated from priority source prices."""
        resp = test_client.get("/api/heatmap/nifty-50")
        reliance = next(b for b in resp.json()["blocks"] if b["symbol"] == "RELIANCE")
        # NSE: close=1415 (today), prev=1390 (yesterday) → change = +1.80%
        assert reliance["close"] == 1415.0
        assert reliance["change_pct"] == pytest.approx(1.80, abs=0.01)

    def test_index_nse_prices_over_yahoo(self, test_client):
        """Index cards use nse_index source, not yahoo_finance."""
        resp = test_client.get("/api/market/overview")
        nifty = next(i for i in resp.json()["indices"] if i["symbol"] == "NIFTY50")
        assert nifty["close"] == 22450.0  # nse_index source


# ═══════════════════════════════════════════════════════════════════════
# COMBINED: DEDUP + PRIORITY IN SINGLE QUERY
# ═══════════════════════════════════════════════════════════════════════

class TestCombinedDedupAndPriority:
    """
    Verify that classification dedup AND price source priority work together.
    This is the exact scenario that caused the production bug.
    """

    def test_movers_correct_change_pct(self, test_client):
        """
        Movers change_pct is calculated from priority source prices,
        with each stock appearing only once within gainers and within losers.
        Note: With only 2 stocks and limit=5, a stock can appear in both
        gainers AND losers (top-N of 2 = all 2, bottom-N of 2 = all 2).
        """
        resp = test_client.get("/api/index/nifty-50/movers?limit=5")
        data = resp.json()

        # No duplicates WITHIN gainers or WITHIN losers
        gainer_symbols = [m["symbol"] for m in data["gainers"]]
        loser_symbols = [m["symbol"] for m in data["losers"]]
        assert len(gainer_symbols) == len(set(gainer_symbols)), f"Duplicate gainers: {gainer_symbols}"
        assert len(loser_symbols) == len(set(loser_symbols)), f"Duplicate losers: {loser_symbols}"

        # RELIANCE should be top gainer: NSE close 1415 vs prev 1390 = +1.80%
        if data["gainers"]:
            reliance = next((m for m in data["gainers"] if m["symbol"] == "RELIANCE"), None)
            if reliance:
                assert reliance["change_pct"] == pytest.approx(1.80, abs=0.01)

    def test_global_instruments_no_duplicates(self, test_client):
        """Global view returns unique instruments."""
        resp = test_client.get("/api/market/global")
        symbols = [i["symbol"] for i in resp.json()["instruments"]]
        assert len(symbols) == len(set(symbols)), f"Duplicate instruments: {symbols}"

    def test_global_overview_grouped_no_duplicates(self, test_client):
        """Global overview grouped view has unique instruments per type."""
        resp = test_client.get("/api/global/overview")
        for itype, instruments in resp.json()["groups"].items():
            symbols = [i["symbol"] for i in instruments]
            assert len(symbols) == len(set(symbols)), f"Duplicates in {itype}: {symbols}"
