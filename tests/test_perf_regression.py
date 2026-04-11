"""
Performance regression tests.

Ensures no endpoint uses the slow best_prices or best_facts_consolidated views
in production queries. These views use correlated subqueries that are O(n²)
on 594K price rows and 2.3M fact rows.

Also tests NIFTY NEXT 50 slug resolution (was returning 404).
"""
import pytest
import re


# ═══════════════════════════════════════════════════════════════════════
# NO SLOW VIEW USAGE IN API MODULES
# ═══════════════════════════════════════════════════════════════════════

class TestNoSlowViews:
    """
    Verify that production API modules don't use the slow correlated subquery views.
    best_prices and best_facts_consolidated are fine in tests but O(n²) on real data.
    """

    # Files that SHOULD NOT use best_prices (replaced with direct price_history queries)
    _PRICE_FILES = [
        "backend/api/market.py",
        "backend/api/index.py",
        "backend/api/instrument.py",
        "backend/api/heatmap.py",
        "backend/api/global_view.py",
        "backend/api/sectors.py",
        "backend/api/charts.py",
    ]

    @pytest.mark.parametrize("filepath", _PRICE_FILES)
    def test_no_best_prices_view(self, filepath):
        """API module must not query best_prices view (too slow on 594K rows)."""
        with open(filepath) as f:
            content = f.read()
        # Allow the string in comments but not in actual SQL queries
        sql_blocks = re.findall(r'""".*?"""', content, re.DOTALL)
        for block in sql_blocks:
            assert "FROM best_prices" not in block, (
                f"{filepath} still uses 'FROM best_prices' in a SQL query. "
                "Use direct price_history query with ROW_NUMBER instead."
            )

    def test_heatmap_no_best_facts_view(self):
        """Heatmap must not use best_facts_consolidated (too slow for market_cap lookup)."""
        with open("backend/api/heatmap.py") as f:
            content = f.read()
        sql_blocks = re.findall(r'""".*?"""', content, re.DOTALL)
        for block in sql_blocks:
            assert "best_facts_consolidated" not in block, (
                "heatmap.py still uses best_facts_consolidated. "
                "Query facts table directly with inline priority ordering."
            )

    def test_search_filter_no_best_facts_view(self):
        """Search filter must not use best_facts_consolidated."""
        with open("backend/api/search.py") as f:
            content = f.read()
        assert "FROM best_facts_consolidated" not in content, (
            "search.py still uses best_facts_consolidated in filter CTEs."
        )


# ═══════════════════════════════════════════════════════════════════════
# NIFTY NEXT 50 SLUG RESOLUTION
# ═══════════════════════════════════════════════════════════════════════

class TestNiftyNext50:
    """Tests for NIFTY NEXT 50 which was returning 404 due to slug mismatch."""

    def test_heatmap_nifty_next_50(self, test_client):
        """Heatmap for nifty-next-50 returns data (was 404)."""
        resp = test_client.get("/api/heatmap/nifty-next-50")
        assert resp.status_code == 200
        data = resp.json()
        assert data["index_name"] == "NIFTY NEXT 50"
        assert len(data["blocks"]) >= 1

    def test_constituents_nifty_next_50(self, test_client):
        """Constituents for nifty-next-50 returns data."""
        resp = test_client.get("/api/index/nifty-next-50/constituents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["index_name"] == "NIFTY NEXT 50"
        assert data["count"] >= 1
        assert data["constituents"][0]["symbol"] == "TCS"

    def test_slug_map_has_all_major_indices(self):
        """Verify slug map covers all major indices."""
        from backend.api.index import _INDEX_SLUG_MAP
        required = [
            "nifty-50", "nifty-bank", "nifty-next-50", "nifty-it",
            "nifty-auto", "nifty-energy", "nifty-psu-bank",
            "nifty-100", "nifty-200", "nifty-500",
        ]
        for slug in required:
            assert slug in _INDEX_SLUG_MAP, f"Missing slug: {slug}"

    def test_slug_map_values_are_uppercase(self):
        """All classification names in slug map should be uppercase (matching DB)."""
        from backend.api.index import _INDEX_SLUG_MAP
        for slug, name in _INDEX_SLUG_MAP.items():
            assert name == name.upper() or any(c.isdigit() for c in name), (
                f"Slug '{slug}' maps to '{name}' — should be uppercase to match DB"
            )


# ═══════════════════════════════════════════════════════════════════════
# TWO-STAGE PRICE RANKING
# ═══════════════════════════════════════════════════════════════════════

class TestTwoStageRanking:
    """
    Verify the two-stage price ranking works:
    Stage 1: Pick best source per (instrument, date)
    Stage 2: Rank by date DESC

    Without two stages, rn=2 could be BSE same-day instead of prev-day NSE.
    """

    def test_change_uses_prev_day_not_alt_source(self, test_client):
        """
        RELIANCE has NSE(1415) + BSE(1417) on 2026-04-10 and NSE(1390) on 2026-04-09.
        Change should be 1415-1390=25 (+1.80%), NOT 1415-1417=-2 (-0.14%).
        """
        resp = test_client.get("/api/index/nifty-50/constituents")
        reliance = next(c for c in resp.json()["constituents"] if c["symbol"] == "RELIANCE")
        assert reliance["change"] == 25.0
        assert reliance["change_pct"] == pytest.approx(1.80, abs=0.01)

    def test_heatmap_change_uses_prev_day(self, test_client):
        """Heatmap change_pct uses previous day, not alternative source."""
        resp = test_client.get("/api/heatmap/nifty-50")
        reliance = next(b for b in resp.json()["blocks"] if b["symbol"] == "RELIANCE")
        assert reliance["change_pct"] == pytest.approx(1.80, abs=0.01)

    def test_index_cards_change_uses_prev_day(self, test_client):
        """Index card change uses previous trading day."""
        resp = test_client.get("/api/market/overview")
        nifty = next(i for i in resp.json()["indices"] if i["symbol"] == "NIFTY50")
        # NIFTY50: 22450 (Apr 10) vs 22300 (Apr 9) = +150 (+0.67%)
        assert nifty["change"] == 150.0
        assert nifty["change_pct"] == pytest.approx(0.67, abs=0.01)
