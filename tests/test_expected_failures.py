"""
Expected failure tests — per project_guidelines.md §2.

Tests that verify the system CORRECTLY handles invalid or problematic input.
These tests assert error responses, not success.

Categories:
1. Invalid input types / missing required fields
2. Database constraint violations
3. Expected skips vs genuine failures (zero denominator = expected skip, not data gap)
4. Malformed requests
5. Out-of-range parameters
6. SQL injection attempts in filter expressions
"""
import pytest


# ═══════════════════════════════════════════════════════════════════════
# 1. INVALID INPUT / MISSING REQUIRED FIELDS
# ═══════════════════════════════════════════════════════════════════════

class TestInvalidInput:
    """Tests for invalid input that should produce clean error responses."""

    def test_observation_missing_required_field_note(self, test_client):
        """POST observation without required 'note' field returns 422."""
        resp = test_client.post("/api/observations", json={
            "data_point_ref": "test:missing:note",
            "data_point_type": "fact",
            "context_json": {},
            # note is missing
        })
        assert resp.status_code == 422  # Pydantic validation error

    def test_observation_missing_required_field_ref(self, test_client):
        """POST observation without required 'data_point_ref' returns 422."""
        resp = test_client.post("/api/observations", json={
            "data_point_type": "fact",
            "context_json": {},
            "note": "test",
        })
        assert resp.status_code == 422

    def test_observation_missing_required_field_type(self, test_client):
        """POST observation without required 'data_point_type' returns 422."""
        resp = test_client.post("/api/observations", json={
            "data_point_ref": "test:ref",
            "context_json": {},
            "note": "test",
        })
        assert resp.status_code == 422

    def test_observation_invalid_context_json_type(self, test_client):
        """POST observation with non-dict context_json returns 422."""
        resp = test_client.post("/api/observations", json={
            "data_point_ref": "test:ref",
            "data_point_type": "fact",
            "context_json": "not a dict",
            "note": "test",
        })
        assert resp.status_code == 422

    def test_pine_execute_missing_script(self, test_client):
        """POST pine/execute without script returns 422."""
        resp = test_client.post("/api/pine/execute", json={
            "symbol": "NIFTY50",
        })
        assert resp.status_code == 422

    def test_pine_execute_missing_symbol(self, test_client):
        """POST pine/execute without symbol returns 422."""
        resp = test_client.post("/api/pine/execute", json={
            "script": "x = sma(close, 2)",
        })
        assert resp.status_code == 422

    def test_filter_missing_expression(self, test_client):
        """POST filter without expression returns 422."""
        resp = test_client.post("/api/search/filter", json={})
        assert resp.status_code == 422

    def test_search_empty_query(self, test_client):
        """Search with empty string violates min_length=1."""
        resp = test_client.get("/api/search/companies?q=")
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# 2. RESOURCE NOT FOUND (404s)
# ═══════════════════════════════════════════════════════════════════════

class TestResourceNotFound:
    """Tests for requesting resources that don't exist."""

    def test_company_404(self, test_client):
        """Company that doesn't exist returns 404."""
        resp = test_client.get("/api/company/ZZZZZZZ")
        assert resp.status_code == 404

    def test_company_financials_404(self, test_client):
        """Financials for nonexistent company returns 404."""
        resp = test_client.get("/api/company/ZZZZZZZ/financials")
        assert resp.status_code == 404

    def test_company_ratios_404(self, test_client):
        """Ratios for nonexistent company returns 404."""
        resp = test_client.get("/api/company/ZZZZZZZ/ratios")
        assert resp.status_code == 404

    def test_company_shareholding_404(self, test_client):
        """Shareholding for nonexistent company returns 404."""
        resp = test_client.get("/api/company/ZZZZZZZ/shareholding")
        assert resp.status_code == 404

    def test_instrument_price_history_404(self, test_client):
        """Price history for nonexistent instrument returns 404."""
        resp = test_client.get("/api/instrument/ZZZZZZZ/price-history")
        assert resp.status_code == 404

    def test_instrument_technicals_404(self, test_client):
        """Technicals for nonexistent instrument returns 404."""
        resp = test_client.get("/api/instrument/ZZZZZZZ/technicals")
        assert resp.status_code == 404

    def test_index_constituents_404(self, test_client):
        """Constituents for nonexistent index returns 404."""
        resp = test_client.get("/api/index/nonexistent-index-xyz/constituents")
        assert resp.status_code == 404

    def test_heatmap_404(self, test_client):
        """Heatmap for nonexistent index returns 404."""
        resp = test_client.get("/api/heatmap/nonexistent-index-xyz")
        assert resp.status_code == 404

    def test_sector_constituents_404(self, test_client):
        """Constituents for nonexistent sector returns 404."""
        resp = test_client.get("/api/sectors/sector/Nonexistent Sector XYZ/constituents")
        assert resp.status_code == 404

    def test_chart_export_404(self, test_client):
        """Chart for nonexistent instrument returns 404."""
        resp = test_client.get("/api/charts/export?symbol=ZZZZZZZ")
        assert resp.status_code == 404

    def test_observation_get_404(self, test_client):
        """GET observation that doesn't exist returns 404."""
        resp = test_client.get("/api/observations/does:not:exist:at:all")
        assert resp.status_code == 404

    def test_observation_delete_404(self, test_client):
        """DELETE observation that doesn't exist returns 404."""
        resp = test_client.delete("/api/observations/does:not:exist:at:all")
        assert resp.status_code == 404

    def test_pine_execute_instrument_404(self, test_client):
        """Pine execute for nonexistent instrument returns 404."""
        resp = test_client.post("/api/pine/execute", json={
            "script": "x = sma(close, 2)",
            "symbol": "ZZZZZZZ",
        })
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# 3. EXPECTED SKIPS vs GENUINE FAILURES
# ═══════════════════════════════════════════════════════════════════════

class TestExpectedSkipsVsGenuineFailures:
    """
    Distinguish "expected to produce no results" from "genuine error."

    Per project_guidelines.md: "test_zero_sales_is_expected_skip_not_missing"
    Zero denominator = expected skip. Missing concept = data gap.
    """

    def test_empty_results_is_not_error(self, test_client):
        """
        Query that matches nothing returns 200 with empty list, NOT 404.
        This is an expected skip (no matching data), not a genuine failure.
        """
        resp = test_client.get("/api/market/flows?participant_type=MF")
        assert resp.status_code == 200  # 200, not 404
        assert resp.json()["flows"] == []  # Empty list, not error

    def test_derivatives_empty_date_is_not_error(self, test_client):
        """
        Querying derivatives for a date with no data returns 200 with empty list.
        Expected skip: the date simply has no data.
        """
        resp = test_client.get("/api/derivatives/participant/1990-01-01")
        assert resp.status_code == 200  # Not 404
        assert resp.json()["positioning"] == []

    def test_pcr_no_data_instrument_is_not_error(self, test_client):
        """
        PCR for instrument with no options data returns 200 empty, not 404.
        Expected: BANKNIFTY has no options data in test fixtures.
        """
        resp = test_client.get("/api/derivatives/pcr?instrument=BANKNIFTY")
        assert resp.status_code == 200
        assert resp.json()["pcr_data"] == []

    def test_oi_no_data_is_not_error(self, test_client):
        """OI changes for instrument with no series OI returns 200 empty."""
        resp = test_client.get("/api/derivatives/oi-changes?instrument=BANKNIFTY")
        assert resp.status_code == 200
        assert resp.json()["oi_data"] == []

    def test_company_no_ratios_is_not_error(self, test_client):
        """
        Company with no ratio data returns 200 with empty ratios.
        Expected skip: TCS has no facts in fixtures.
        """
        resp = test_client.get("/api/company/TCS/ratios")
        assert resp.status_code == 200  # Not 404 — company exists, just no ratio data
        assert resp.json()["ratios"] == []

    def test_company_no_shareholding_is_not_error(self, test_client):
        """Company with no shareholding data returns 200 empty."""
        resp = test_client.get("/api/company/TCS/shareholding")
        assert resp.status_code == 200
        assert resp.json()["shareholding"] == []

    def test_company_no_peers_is_not_error(self, test_client):
        """Company with no sector classification returns 200 with null sector."""
        resp = test_client.get("/api/company/TCS/peers")
        assert resp.status_code == 200
        assert resp.json()["sector"] is None  # Expected: TCS has no sector in fixtures
        assert resp.json()["peers"] == []

    def test_sector_performance_empty_type_is_not_error(self, test_client):
        """Performance for classification_type with no data returns 200 empty."""
        resp = test_client.get("/api/sectors/performance?classification_type=business_group")
        assert resp.status_code == 200
        assert resp.json()["performance"] == []

    def test_search_no_results_is_not_error(self, test_client):
        """Search with no matches returns 200 with count=0, not 404."""
        resp = test_client.get("/api/search/companies?q=ZZZZZZZ")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_filter_no_match_is_not_error(self, test_client):
        """Filter that matches nothing returns 200 with count=0."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "sales > 9999999999"
        })
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_genuine_failure_nonexistent_company_is_404(self, test_client):
        """
        Requesting financials for a company that doesn't exist IS a genuine failure.
        Contrast with TCS (exists but has no data) → 200.
        """
        resp_genuine = test_client.get("/api/company/ZZZZZZZ/financials")
        assert resp_genuine.status_code == 404  # Genuine: company doesn't exist

        resp_expected = test_client.get("/api/company/TCS/financials")
        assert resp_expected.status_code == 200  # Expected skip: company exists, no data

    def test_genuine_failure_nonexistent_index_is_404(self, test_client):
        """
        Nonexistent index is a genuine failure (404).
        Contrast with valid index that has no technicals data (200 with empty).
        """
        resp = test_client.get("/api/index/nonexistent-xyz/constituents")
        assert resp.status_code == 404

    def test_null_period_end_date_does_not_crash(self, test_client):
        """
        Facts with NULL period_end_date (e.g., snapshot market_cap) should not
        crash the financials endpoint. Regression: TypeError '<' not supported
        between instances of 'NoneType' and 'str' when sorting periods.
        """
        resp = test_client.get("/api/company/RELIANCE/financials")
        assert resp.status_code == 200
        # None should be excluded from periods list
        for period in resp.json()["periods"]:
            assert period is not None


# ═══════════════════════════════════════════════════════════════════════
# 4. PINE SCRIPT EXPECTED COMPILATION/RUNTIME FAILURES
# ═══════════════════════════════════════════════════════════════════════

class TestPineExpectedFailures:
    """Pine Script errors that should produce clean 400 responses."""

    def test_syntax_error_unexpected_char(self, test_client):
        """Unexpected character in script returns 400 with message."""
        resp = test_client.post("/api/pine/execute", json={
            "script": "x = @invalid",
            "symbol": "NIFTY50",
        })
        assert resp.status_code == 400
        assert "Script error" in resp.json()["detail"]

    def test_undefined_variable(self, test_client):
        """Reference to undefined variable returns 400."""
        resp = test_client.post("/api/pine/execute", json={
            "script": "x = undefined_var + 1",
            "symbol": "NIFTY50",
        })
        assert resp.status_code == 400
        assert "Undefined variable" in resp.json()["detail"]

    def test_unknown_builtin_function(self, test_client):
        """Call to unknown function returns 400."""
        resp = test_client.post("/api/pine/execute", json={
            "script": "x = nonexistent_func(close, 20)",
            "symbol": "NIFTY50",
        })
        assert resp.status_code == 400
        assert "Unknown function" in resp.json()["detail"]

    def test_wrong_argument_count(self, test_client):
        """Wrong number of arguments returns 400."""
        resp = test_client.post("/api/pine/execute", json={
            "script": "x = sma(close)",  # sma needs 2 args
            "symbol": "NIFTY50",
        })
        assert resp.status_code == 400
        assert "expects 2 args" in resp.json()["detail"]

    def test_empty_script_returns_400(self, test_client):
        """Empty script (no assignments) returns 400."""
        resp = test_client.post("/api/pine/execute", json={
            "script": "",
            "symbol": "NIFTY50",
        })
        assert resp.status_code == 400

    def test_comment_only_script_returns_400(self, test_client):
        """Script with only comments (no output) returns 400."""
        resp = test_client.post("/api/pine/execute", json={
            "script": "// just a comment",
            "symbol": "NIFTY50",
        })
        assert resp.status_code == 400
        assert "no outputs" in resp.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════
# 5. FILTER PARSER EXPECTED FAILURES
# ═══════════════════════════════════════════════════════════════════════

class TestFilterExpectedFailures:
    """Filter expressions that should parse but produce errors or empty results."""

    def test_unknown_concept_produces_parse_error(self, test_client):
        """Unknown concept in filter produces parse_error, not crash."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "Filter: xyzabc123 > 100"
        })
        assert resp.status_code == 200  # Not 500
        assert len(resp.json()["parse_errors"]) >= 1

    def test_unparseable_expression_produces_parse_error(self, test_client):
        """Completely unparseable text produces parse_error."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "Filter: hello world no operators"
        })
        assert resp.status_code == 200
        assert len(resp.json()["parse_errors"]) >= 1
        assert resp.json()["count"] == 0

    def test_mixed_valid_and_invalid_conditions(self, test_client):
        """Mix of valid and invalid conditions: valid ones execute, invalid ones logged as errors."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "Filter: sales > 50000, xyzabc > 100"
        })
        assert resp.status_code == 200
        data = resp.json()
        # Should have 1 valid condition and 1 parse error
        assert len(data["parsed_conditions"]) >= 1
        assert len(data["parse_errors"]) >= 1

    def test_sql_injection_in_filter(self, test_client):
        """SQL injection attempt in filter is safely handled (concept aliases are controlled)."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "Filter: sales' OR 1=1-- > 100"
        })
        assert resp.status_code == 200
        # Should produce parse error, not execute injected SQL
        assert resp.json()["count"] == 0


# ═══════════════════════════════════════════════════════════════════════
# 6. OBSERVATION CONSTRAINT VIOLATIONS
# ═══════════════════════════════════════════════════════════════════════

class TestObservationConstraints:
    """Test that constraint violations are handled cleanly."""

    def test_duplicate_ref_is_upsert_not_error(self, test_client):
        """
        Inserting same data_point_ref twice is an UPSERT, not a constraint violation.
        This is by design (idempotency).
        """
        ref = "constraint:test:upsert"
        r1 = test_client.post("/api/observations", json={
            "data_point_ref": ref, "data_point_type": "fact",
            "context_json": {}, "note": "first",
        })
        assert r1.json()["status"] == "created"

        r2 = test_client.post("/api/observations", json={
            "data_point_ref": ref, "data_point_type": "fact",
            "context_json": {}, "note": "second",
        })
        assert r2.json()["status"] == "updated"  # Upsert, not error

    def test_delete_then_recreate(self, test_client):
        """Delete then re-create with same ref works (no ghost constraint)."""
        ref = "constraint:test:recreate"
        test_client.post("/api/observations", json={
            "data_point_ref": ref, "data_point_type": "fact",
            "context_json": {}, "note": "original",
        })
        test_client.delete(f"/api/observations/{ref}")

        # Re-create with same ref
        resp = test_client.post("/api/observations", json={
            "data_point_ref": ref, "data_point_type": "fact",
            "context_json": {}, "note": "recreated",
        })
        assert resp.json()["status"] == "created"  # Fresh create, not update

        # Verify no stale history
        obs = test_client.get(f"/api/observations/{ref}").json()
        assert obs["observation"]["note"] == "recreated"
        assert obs["history"] == []  # History was deleted with the observation
