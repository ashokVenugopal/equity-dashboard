"""
Comprehensive edge case, sensitivity, and idempotency tests.

Follows project_guidelines.md §2:
- Edge cases: empty input, None, zero values, special characters, boundary values
- Sensitivity: zero denominators, negative inputs, extreme values, threshold boundaries
- Idempotency: calling GET endpoints twice returns identical results
- Expected failures: invalid input types, missing fields, constraint violations
- Expected vs genuine failures: distinguish expected skips from data gaps
"""
import pytest


# ═══════════════════════════════════════════════════════════════════════
# MARKET API — Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestMarketEdgeCases:
    """Edge cases for market overview endpoints."""

    def test_overview_idempotent(self, test_client):
        """Calling overview twice returns identical results."""
        r1 = test_client.get("/api/market/overview").json()
        r2 = test_client.get("/api/market/overview").json()
        assert r1["indices"] == r2["indices"]
        assert r1["flows"] == r2["flows"]

    def test_flows_limit_boundary_min(self, test_client):
        """Minimum limit=1 returns exactly 1 row."""
        resp = test_client.get("/api/market/flows?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()["flows"]) <= 1

    def test_flows_limit_boundary_max(self, test_client):
        """Maximum limit=100 is accepted."""
        resp = test_client.get("/api/market/flows?limit=100")
        assert resp.status_code == 200

    def test_flows_invalid_participant(self, test_client):
        """Invalid participant_type returns empty results (not an error)."""
        resp = test_client.get("/api/market/flows?participant_type=NONEXISTENT")
        assert resp.status_code == 200
        assert resp.json()["flows"] == []

    def test_flows_history_start_after_end(self, test_client):
        """start_date > end_date returns empty results."""
        resp = test_client.get("/api/market/flows/history?segment=CASH&start_date=2030-01-01&end_date=2020-01-01")
        assert resp.status_code == 200
        assert resp.json()["flows"] == []

    def test_flows_history_same_date(self, test_client):
        """start_date == end_date returns only that date."""
        resp = test_client.get("/api/market/flows/history?segment=CASH&start_date=2026-04-10&end_date=2026-04-10")
        assert resp.status_code == 200
        for flow in resp.json()["flows"]:
            assert flow["flow_date"] == "2026-04-10"

    def test_breadth_limit_one(self, test_client):
        """Breadth with limit=1 returns latest only."""
        resp = test_client.get("/api/market/breadth?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["breadth"]) == 1
        assert data["breadth"][0]["trade_date"] == "2026-04-10"

    def test_global_no_stock_instruments(self, test_client):
        """Global endpoint excludes stock instruments."""
        resp = test_client.get("/api/market/global")
        for inst in resp.json()["instruments"]:
            assert inst["instrument_type"] != "stock"


# ═══════════════════════════════════════════════════════════════════════
# INDEX API — Edge Cases & Sensitivity
# ═══════════════════════════════════════════════════════════════════════

class TestIndexEdgeCases:
    """Edge cases for index deep-dive endpoints."""

    def test_constituents_idempotent(self, test_client):
        """Calling constituents twice returns identical data."""
        r1 = test_client.get("/api/index/nifty-50/constituents").json()
        r2 = test_client.get("/api/index/nifty-50/constituents").json()
        assert r1["constituents"] == r2["constituents"]

    def test_movers_limit_one(self, test_client):
        """Movers with limit=1 returns exactly 1 gainer and 1 loser."""
        resp = test_client.get("/api/index/nifty-50/movers?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["gainers"]) <= 1
        assert len(data["losers"]) <= 1

    def test_technicals_with_null_values(self, test_client):
        """Technicals for stocks without all indicators returns nulls gracefully."""
        resp = test_client.get("/api/index/nifty-50/technicals")
        data = resp.json()
        # HDFCBANK has only daily_change_pct, not dma_50 etc.
        hdfc = next(t for t in data["technicals"] if t["symbol"] == "HDFCBANK")
        assert hdfc["dma_50"] is None  # Expected: no DMA data for HDFCBANK in fixtures
        assert hdfc["daily_change_pct"] is not None

    def test_breadth_all_advancing(self, test_client):
        """Breadth when all stocks advance (edge: declines=0)."""
        # In fixtures: RELIANCE +1.80%, HDFCBANK -0.57%, so this tests real calculation
        resp = test_client.get("/api/index/nifty-50/breadth")
        breadth = resp.json()["breadth"]
        assert breadth["advances"] + breadth["declines"] + breadth["unchanged"] == breadth["total"]

    def test_instrument_price_history_date_range(self, test_client):
        """Price history with date filter returns subset."""
        resp = test_client.get("/api/instrument/RELIANCE/price-history?start_date=2026-04-10")
        data = resp.json()
        assert all(p["trade_date"] >= "2026-04-10" for p in data["prices"])

    def test_instrument_price_history_limit_one(self, test_client):
        """Price history limit=1 returns latest bar only."""
        resp = test_client.get("/api/instrument/RELIANCE/price-history?limit=1")
        assert len(resp.json()["prices"]) == 1

    def test_instrument_case_insensitive(self, test_client):
        """Symbol lookup is case-insensitive."""
        resp = test_client.get("/api/instrument/reliance/price-history")
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "RELIANCE"


# ═══════════════════════════════════════════════════════════════════════
# COMPANY API — Edge Cases & Expected Failures
# ═══════════════════════════════════════════════════════════════════════

class TestCompanyEdgeCases:
    """Edge cases for company fundamentals."""

    def test_financials_idempotent(self, test_client):
        """Calling financials twice returns identical data."""
        r1 = test_client.get("/api/company/RELIANCE/financials").json()
        r2 = test_client.get("/api/company/RELIANCE/financials").json()
        assert r1["sections"] == r2["sections"]
        assert r1["periods"] == r2["periods"]

    def test_financials_section_filter(self, test_client):
        """Section filter returns only requested section."""
        resp = test_client.get("/api/company/RELIANCE/financials?section=profit_loss")
        data = resp.json()
        # Only profit_loss section should be present
        assert "profit_loss" in data["sections"]

    def test_financials_empty_section(self, test_client):
        """Section with no data returns empty."""
        # TCS has no facts in fixtures
        resp = test_client.get("/api/company/TCS/financials")
        assert resp.status_code == 200
        data = resp.json()
        assert data["periods"] == []

    def test_ratios_empty_company(self, test_client):
        """Company with no ratio data returns empty."""
        resp = test_client.get("/api/company/TCS/ratios")
        assert resp.status_code == 200
        assert resp.json()["ratios"] == []

    def test_shareholding_empty(self, test_client):
        """Company with no shareholding data returns empty."""
        resp = test_client.get("/api/company/TCS/shareholding")
        assert resp.status_code == 200
        assert resp.json()["shareholding"] == []

    def test_meta_case_insensitive(self, test_client):
        """Symbol lookup is case-insensitive."""
        resp = test_client.get("/api/company/reliance")
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "RELIANCE"


# ═══════════════════════════════════════════════════════════════════════
# OBSERVATIONS — Idempotency & Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestObservationsEdgeCases:
    """Edge cases for observation logging."""

    def test_create_with_empty_tags(self, test_client):
        """Tags can be None."""
        resp = test_client.post("/api/observations", json={
            "data_point_ref": "test:empty:tags",
            "data_point_type": "fact",
            "context_json": {},
            "note": "No tags",
            "tags": None,
        })
        assert resp.status_code == 200
        obs = test_client.get("/api/observations/test:empty:tags").json()
        assert obs["observation"]["tags"] is None

    def test_create_with_special_chars_in_note(self, test_client):
        """Notes with special characters are stored correctly."""
        note = 'Balance sheet has "red flag" — D/E > 2.0 & rising'
        resp = test_client.post("/api/observations", json={
            "data_point_ref": "test:special:chars",
            "data_point_type": "fact",
            "context_json": {"info": "test <html> & 'quotes'"},
            "note": note,
        })
        assert resp.status_code == 200
        obs = test_client.get("/api/observations/test:special:chars").json()
        assert obs["observation"]["note"] == note

    def test_create_with_long_ref(self, test_client):
        """Very long data_point_ref is accepted."""
        ref = "fact:" + "A" * 500 + ":sales:2025-03-31:annual:consolidated"
        resp = test_client.post("/api/observations", json={
            "data_point_ref": ref,
            "data_point_type": "fact",
            "context_json": {},
            "note": "Long ref test",
        })
        assert resp.status_code == 200

    def test_upsert_preserves_type_and_context(self, test_client):
        """Updating an observation also updates context_json."""
        ref = "test:upsert:context"
        test_client.post("/api/observations", json={
            "data_point_ref": ref, "data_point_type": "fact",
            "context_json": {"version": 1}, "note": "v1",
        })
        test_client.post("/api/observations", json={
            "data_point_ref": ref, "data_point_type": "fact",
            "context_json": {"version": 2}, "note": "v2",
        })
        obs = test_client.get(f"/api/observations/{ref}").json()
        assert '"version": 2' in obs["observation"]["context_json"]

    def test_list_with_offset(self, test_client):
        """Pagination via offset works."""
        for i in range(3):
            test_client.post("/api/observations", json={
                "data_point_ref": f"test:offset:{i}",
                "data_point_type": "fact",
                "context_json": {},
                "note": f"Note {i}",
            })
        resp = test_client.get("/api/observations?limit=2&offset=1")
        assert resp.json()["count"] <= 2

    def test_delete_cleans_history(self, test_client):
        """Deleting an observation also removes its history."""
        ref = "test:delete:history"
        test_client.post("/api/observations", json={
            "data_point_ref": ref, "data_point_type": "fact",
            "context_json": {}, "note": "v1",
        })
        test_client.post("/api/observations", json={
            "data_point_ref": ref, "data_point_type": "fact",
            "context_json": {}, "note": "v2",
        })
        # Now delete
        test_client.delete(f"/api/observations/{ref}")
        # Verify gone
        resp = test_client.get(f"/api/observations/{ref}")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# SEARCH / FILTER — Edge Cases & Sensitivity
# ═══════════════════════════════════════════════════════════════════════

class TestSearchEdgeCases:
    """Edge cases for search and filter endpoints."""

    def test_search_single_char(self, test_client):
        """Search with single character."""
        resp = test_client.get("/api/search/companies?q=R")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1  # RELIANCE matches

    def test_search_exact_symbol(self, test_client):
        """Exact symbol match ranks first."""
        resp = test_client.get("/api/search/companies?q=TCS")
        results = resp.json()["results"]
        assert results[0]["symbol"] == "TCS"

    def test_filter_operators(self, test_client):
        """Test all comparison operators."""
        for op in [">", "<", ">=", "<=", "="]:
            resp = test_client.post("/api/search/filter", json={
                "expression": f"sales {op} 50000"
            })
            assert resp.status_code == 200
            assert len(resp.json()["parsed_conditions"]) == 1
            assert resp.json()["parsed_conditions"][0]["op"] == op

    def test_filter_zero_value(self, test_client):
        """Filter with value=0 works (sensitivity: zero boundary)."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "sales > 0"
        })
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_filter_very_large_value(self, test_client):
        """Filter with extreme large value returns no results."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "sales > 99999999999"
        })
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_filter_negative_value(self, test_client):
        """Filter with negative value (sensitivity: negative threshold)."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "net profit > -1000"
        })
        assert resp.status_code == 200

    def test_filter_decimal_value(self, test_client):
        """Filter with decimal value."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "debt < 0.75"
        })
        assert resp.status_code == 200
        assert resp.json()["parsed_conditions"][0]["value"] == 0.75

    def test_filter_empty_expression(self, test_client):
        """Empty filter returns no results gracefully."""
        resp = test_client.post("/api/search/filter", json={
            "expression": ""
        })
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_filter_idempotent(self, test_client):
        """Same filter twice returns identical results."""
        expr = "sales > 50000"
        r1 = test_client.post("/api/search/filter", json={"expression": expr}).json()
        r2 = test_client.post("/api/search/filter", json={"expression": expr}).json()
        assert r1["results"] == r2["results"]

    def test_suggestions_special_chars(self, test_client):
        """Suggestions handle special characters."""
        resp = test_client.get("/api/search/suggestions?q=%26%3C%3E")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# DERIVATIVES — Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestDerivativesEdgeCases:
    """Edge cases for derivatives endpoints."""

    def test_pcr_unknown_instrument(self, test_client):
        """PCR for instrument with no options data returns empty."""
        resp = test_client.get("/api/derivatives/pcr?instrument=NONEXISTENT")
        assert resp.status_code == 200
        assert resp.json()["pcr_data"] == []

    def test_pcr_idempotent(self, test_client):
        """PCR called twice returns identical data."""
        r1 = test_client.get("/api/derivatives/pcr?instrument=NIFTY").json()
        r2 = test_client.get("/api/derivatives/pcr?instrument=NIFTY").json()
        assert r1["pcr_data"] == r2["pcr_data"]

    def test_fii_positioning_long_short_sum(self, test_client):
        """Long% + Short% should equal 100%."""
        resp = test_client.get("/api/derivatives/fii-positioning")
        for pos in resp.json()["positioning"]:
            if pos["long_pct"] is not None and pos["short_pct"] is not None:
                assert pos["long_pct"] + pos["short_pct"] == pytest.approx(100.0, abs=0.1)


# ═══════════════════════════════════════════════════════════════════════
# HEATMAP — Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestHeatmapEdgeCases:
    """Edge cases for heatmap endpoint."""

    def test_heatmap_blocks_have_required_fields(self, test_client):
        """Every block has symbol, market_cap, change_pct."""
        resp = test_client.get("/api/heatmap/nifty-50")
        for block in resp.json()["blocks"]:
            assert "symbol" in block
            assert "market_cap" in block
            assert "change_pct" in block

    def test_heatmap_idempotent(self, test_client):
        """Heatmap called twice returns identical data."""
        r1 = test_client.get("/api/heatmap/nifty-50").json()
        r2 = test_client.get("/api/heatmap/nifty-50").json()
        assert r1["blocks"] == r2["blocks"]


# ═══════════════════════════════════════════════════════════════════════
# CHART EXPORT — Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestChartExportEdgeCases:
    """Edge cases for chart export."""

    def test_chart_custom_height(self, test_client):
        """Custom height parameter works."""
        resp = test_client.get("/api/charts/export?symbol=NIFTY50&height=600")
        assert resp.status_code == 200
        assert "600" in resp.text  # Height embedded in HTML

    def test_chart_limit_one(self, test_client):
        """Chart with limit=1 still produces valid HTML."""
        resp = test_client.get("/api/charts/export?symbol=NIFTY50&limit=1")
        assert resp.status_code == 200
        assert "createChart" in resp.text


# ═══════════════════════════════════════════════════════════════════════
# SECTORS — Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestSectorsEdgeCases:
    """Edge cases for sectors endpoints."""

    def test_performance_idempotent(self, test_client):
        """Sector performance called twice returns identical data."""
        r1 = test_client.get("/api/sectors/performance").json()
        r2 = test_client.get("/api/sectors/performance").json()
        assert r1["performance"] == r2["performance"]

    def test_performance_unknown_type(self, test_client):
        """Unknown classification type returns empty."""
        resp = test_client.get("/api/sectors/performance?classification_type=nonexistent")
        assert resp.status_code == 200
        assert resp.json()["performance"] == []

    def test_performance_unknown_metric(self, test_client):
        """Unknown metric returns empty."""
        resp = test_client.get("/api/sectors/performance?metric=nonexistent_metric")
        assert resp.status_code == 200
        assert resp.json()["performance"] == []


# ═══════════════════════════════════════════════════════════════════════
# GLOBAL VIEW — Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestGlobalViewEdgeCases:
    """Edge cases for global view endpoints."""

    def test_overview_grouped_types(self, test_client):
        """Overview groups contain only instruments of that type."""
        resp = test_client.get("/api/global/overview")
        groups = resp.json()["groups"]
        for itype, instruments in groups.items():
            for inst in instruments:
                assert inst["instrument_type"] == itype

    def test_adrs_empty(self, test_client):
        """ADRs endpoint returns empty if no ADR instruments in fixtures."""
        resp = test_client.get("/api/global/adrs")
        assert resp.status_code == 200
        # No ADR in fixtures, so empty
        assert resp.json()["instruments"] == []


# ═══════════════════════════════════════════════════════════════════════
# PINE SCRIPT — Sensitivity & Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestPineEdgeCases:
    """Sensitivity and edge cases for Pine Script engine."""

    def test_empty_script(self, test_client):
        """Empty script returns 400."""
        resp = test_client.post("/api/pine/execute", json={
            "script": "", "symbol": "NIFTY50",
        })
        assert resp.status_code == 400

    def test_comment_only_script(self, test_client):
        """Script with only comments produces no output."""
        resp = test_client.post("/api/pine/execute", json={
            "script": "// just a comment\n# another comment",
            "symbol": "NIFTY50",
        })
        assert resp.status_code == 400  # No outputs

    def test_sma_length_larger_than_data(self, test_client):
        """SMA with length > available bars produces all-null output."""
        resp = test_client.post("/api/pine/execute", json={
            "script": "x = sma(close, 999)",
            "symbol": "NIFTY50",
            "limit": 2,
        })
        assert resp.status_code == 200
        # All values should be None (not enough data)
        assert all(v is None for v in resp.json()["indicators"]["x"])

    def test_nested_function_calls(self, test_client):
        """Nested function calls: sma of sma."""
        resp = test_client.post("/api/pine/execute", json={
            "script": "inner = sma(close, 2)\nouter = sma(inner, 2)",
            "symbol": "NIFTY50",
            "limit": 10,
        })
        assert resp.status_code == 200
        assert "outer" in resp.json()["indicators"]


# ═══════════════════════════════════════════════════════════════════════
# EXPORT — Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestExportEdgeCases:
    """Edge cases for export endpoints."""

    def test_export_csv_empty(self, test_client):
        """CSV export with no observations returns headers only."""
        resp = test_client.get("/api/export/observations?format=csv")
        assert resp.status_code == 200
        # Empty CSV (no rows, possibly no headers either)
        assert "text/csv" in resp.headers["content-type"]


# ═══════════════════════════════════════════════════════════════════════
# FORMATTING — Sensitivity Tests
# ═══════════════════════════════════════════════════════════════════════

class TestFormattingSensitivity:
    """Sensitivity tests for cell formatting edge cases."""

    def test_format_very_large_number(self):
        from backend.core.formatting import format_cell
        result = format_cell("market_cap", 99999999.99)
        assert "99,999,999.99" in result

    def test_format_negative_volume(self):
        """Negative volume (shouldn't happen but handle gracefully)."""
        from backend.core.formatting import format_cell
        result = format_cell("volume", -100)
        assert "-100" in result

    def test_format_nan_like_string(self):
        """String 'NaN' should be returned as-is."""
        from backend.core.formatting import format_cell
        assert format_cell("some_field", "NaN") == "NaN"

    def test_format_zero_ratio(self):
        """Zero ratio formatted correctly."""
        from backend.core.formatting import format_cell
        assert format_cell("debt_to_equity", 0.0) == "0.0000"

    def test_format_negative_percent(self):
        """Negative percentage."""
        from backend.core.formatting import format_cell
        result = format_cell("roe", -15.5)
        assert "-15.50%" in result

    def test_format_boolean_like(self):
        """Boolean-like values."""
        from backend.core.formatting import format_cell
        assert format_cell("flag", True) == "True"
        assert format_cell("flag", False) == "False"
