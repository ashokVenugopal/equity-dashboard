"""
Tests for screener unit annotations and derived ratio aliases.

Per project_guidelines.md §2:
1. Core happy path — units returned with parsed conditions
2. Variations — different concept units (percent, ratio, inr_cr, inr, days)
3. Edge cases — unknown concepts, mixed valid/invalid, empty expression
4. Expected failures — missing expression (422), sql injection
5. Sensitivity — all new aliases resolve to correct concept codes
6. Idempotency — same query returns same results
7. Expected failures vs genuine failures — unknown concept = parse error, not crash
"""
import pytest


# ═══════════════════════════════════════════════════════════════════════
# 1. UNIT ANNOTATIONS — HAPPY PATH
# ═══════════════════════════════════════════════════════════════════════

class TestUnitAnnotations:
    def test_ratio_unit_returned(self, test_client):
        """PEG is a ratio — unit should be 'ratio'."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "peg < 2"
        })
        data = resp.json()
        assert len(data["parsed_conditions"]) == 1
        assert data["parsed_conditions"][0]["unit"] == "ratio"

    def test_percent_unit_returned(self, test_client):
        """ROE is a percent — unit should be 'percent'."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "roe > 10"
        })
        data = resp.json()
        assert data["parsed_conditions"][0]["unit"] == "percent"

    def test_inr_cr_unit_returned(self, test_client):
        """Sales is in crores — unit should be 'inr_cr'."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "sales > 1000"
        })
        data = resp.json()
        assert data["parsed_conditions"][0]["unit"] == "inr_cr"

    def test_inr_unit_returned(self, test_client):
        """EPS is in rupees — unit should be 'inr'."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "eps > 10"
        })
        data = resp.json()
        assert data["parsed_conditions"][0]["unit"] == "inr"

    def test_days_unit_returned(self, test_client):
        """Debtor days — unit should be 'days'."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "debtor days < 90"
        })
        data = resp.json()
        assert data["parsed_conditions"][0]["unit"] == "days"

    def test_multiple_conditions_all_have_units(self, test_client):
        """Each condition in a multi-condition filter has a unit."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "pe < 20, roe > 15, sales > 5000"
        })
        data = resp.json()
        assert len(data["parsed_conditions"]) == 3
        for cond in data["parsed_conditions"]:
            assert "unit" in cond
            assert cond["unit"] is not None

    def test_unknown_concept_no_unit(self, test_client):
        """Unknown concept doesn't crash — produces parse error, no conditions."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "xyzabc > 100"
        })
        data = resp.json()
        assert len(data["parsed_conditions"]) == 0
        assert len(data["parse_errors"]) >= 1


# ═══════════════════════════════════════════════════════════════════════
# 2. NEW ALIAS RESOLUTION — GROWTH CONCEPTS
# ═══════════════════════════════════════════════════════════════════════

class TestGrowthAliases:
    def test_profit_growth_maps_to_screener_3y(self, test_client):
        """'profit growth' should resolve to screener_profit_growth_3y."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "profit growth > 20"
        })
        data = resp.json()
        assert data["parsed_conditions"][0]["concept_code"] == "screener_profit_growth_3y"

    def test_pat_growth_alias(self, test_client):
        """'pat growth' should also resolve to screener_profit_growth_3y."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "pat growth > 20"
        })
        data = resp.json()
        assert data["parsed_conditions"][0]["concept_code"] == "screener_profit_growth_3y"

    def test_earnings_growth_alias(self, test_client):
        """'earnings growth' → screener_profit_growth_3y."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "earnings growth > 15"
        })
        data = resp.json()
        assert data["parsed_conditions"][0]["concept_code"] == "screener_profit_growth_3y"

    def test_sales_growth_maps_to_screener_3y(self, test_client):
        """'sales growth' → screener_sales_growth_3y."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "sales growth > 10"
        })
        data = resp.json()
        assert data["parsed_conditions"][0]["concept_code"] == "screener_sales_growth_3y"

    def test_profit_growth_5y_alias(self, test_client):
        """'profit growth 5y' → screener_profit_growth_5y."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "profit growth 5y > 15"
        })
        data = resp.json()
        assert data["parsed_conditions"][0]["concept_code"] == "screener_profit_growth_5y"

    def test_sales_growth_ttm_alias(self, test_client):
        """'sales growth ttm' → screener_sales_growth_ttm."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "sales growth ttm > 10"
        })
        data = resp.json()
        assert data["parsed_conditions"][0]["concept_code"] == "screener_sales_growth_ttm"


# ═══════════════════════════════════════════════════════════════════════
# 3. NEW ALIAS RESOLUTION — DERIVED RATIOS
# ═══════════════════════════════════════════════════════════════════════

class TestDerivedRatioAliases:
    def test_peg_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "peg < 1"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "peg_ratio"

    def test_pb_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "p/b < 3"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "price_to_book"

    def test_ps_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "p/s < 5"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "price_to_sales"

    def test_ev_ebitda_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "ev/ebitda < 15"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "ev_ebitda"

    def test_ev_ebitda_space_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "ev ebitda < 15"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "ev_ebitda"

    def test_roa_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "roa > 5"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "return_on_assets"

    def test_interest_coverage_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "interest coverage > 3"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "interest_coverage"

    def test_dividend_payout_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "dividend payout < 50"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "dividend_payout"

    def test_payout_ratio_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "payout ratio < 50"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "dividend_payout"

    def test_fcf_margin_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "fcf margin > 10"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "fcf_to_sales"

    def test_asset_turnover_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "asset turnover > 1"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "asset_turnover"

    def test_fixed_asset_turnover_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "fixed asset turnover > 2"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "fixed_asset_turnover"

    def test_gross_margin_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "gross margin > 30"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "gross_margin"

    def test_equity_multiplier_alias(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "equity multiplier < 3"})
        assert resp.json()["parsed_conditions"][0]["concept_code"] == "equity_multiplier"


# ═══════════════════════════════════════════════════════════════════════
# 4. OPERATOR VARIATIONS
# ═══════════════════════════════════════════════════════════════════════

class TestOperatorVariations:
    def test_less_than(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "pe < 20"})
        assert resp.json()["parsed_conditions"][0]["op"] == "<"

    def test_greater_than(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "pe > 20"})
        assert resp.json()["parsed_conditions"][0]["op"] == ">"

    def test_less_than_or_equal(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "pe <= 20"})
        assert resp.json()["parsed_conditions"][0]["op"] == "<="

    def test_greater_than_or_equal(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "pe >= 20"})
        assert resp.json()["parsed_conditions"][0]["op"] == ">="

    def test_equals(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "pe = 20"})
        assert resp.json()["parsed_conditions"][0]["op"] == "="

    def test_not_equals(self, test_client):
        resp = test_client.post("/api/search/filter", json={"expression": "pe != 20"})
        assert resp.json()["parsed_conditions"][0]["op"] == "!="

    def test_no_spaces(self, test_client):
        """'peg<1' (no spaces) should still parse correctly."""
        resp = test_client.post("/api/search/filter", json={"expression": "peg<1"})
        data = resp.json()
        assert len(data["parsed_conditions"]) == 1
        assert data["parsed_conditions"][0]["concept_code"] == "peg_ratio"
        assert data["parsed_conditions"][0]["op"] == "<"
        assert data["parsed_conditions"][0]["value"] == 1.0

    def test_decimal_value(self, test_client):
        """Decimal values parse correctly."""
        resp = test_client.post("/api/search/filter", json={"expression": "debt < 0.5"})
        assert resp.json()["parsed_conditions"][0]["value"] == 0.5


# ═══════════════════════════════════════════════════════════════════════
# 5. EDGE CASES
# ═══════════════════════════════════════════════════════════════════════

class TestScreenerEdgeCases:
    def test_filter_prefix_stripped(self, test_client):
        """'Filter:' prefix is optional and stripped."""
        r1 = test_client.post("/api/search/filter", json={"expression": "Filter: pe < 20"})
        r2 = test_client.post("/api/search/filter", json={"expression": "pe < 20"})
        assert r1.json()["parsed_conditions"] == r2.json()["parsed_conditions"]

    def test_whitespace_handling(self, test_client):
        """Extra whitespace doesn't break parsing."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "  pe  <  20  ,  roe  >  15  "
        })
        data = resp.json()
        assert len(data["parsed_conditions"]) == 2

    def test_mixed_valid_invalid(self, test_client):
        """Valid + invalid conditions: valid ones parse, invalid ones error."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "pe < 20, xyzabc > 5, roe > 15"
        })
        data = resp.json()
        assert len(data["parsed_conditions"]) == 2
        assert len(data["parse_errors"]) == 1

    def test_empty_expression_422(self, test_client):
        """Empty expression body returns 422."""
        resp = test_client.post("/api/search/filter", json={})
        assert resp.status_code == 422

    def test_only_commas(self, test_client):
        """Expression of only commas returns 0 results, no crash."""
        resp = test_client.post("/api/search/filter", json={"expression": ", , ,"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_single_concept_no_operator(self, test_client):
        """Just a concept name without operator → parse error."""
        resp = test_client.post("/api/search/filter", json={"expression": "pe"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_sql_injection_in_concept(self, test_client):
        """SQL injection attempt is safely handled."""
        resp = test_client.post("/api/search/filter", json={
            "expression": "pe' OR 1=1-- > 10"
        })
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


# ═══════════════════════════════════════════════════════════════════════
# 6. IDEMPOTENCY
# ═══════════════════════════════════════════════════════════════════════

class TestScreenerIdempotency:
    def test_same_query_same_results(self, test_client):
        """Running the same filter twice returns identical results."""
        body = {"expression": "sales > 50000"}
        r1 = test_client.post("/api/search/filter", json=body).json()
        r2 = test_client.post("/api/search/filter", json=body).json()
        assert r1["count"] == r2["count"]
        assert r1["results"] == r2["results"]
        assert r1["parsed_conditions"] == r2["parsed_conditions"]


# ═══════════════════════════════════════════════════════════════════════
# 7. CONCEPT SUGGESTIONS ENDPOINT
# ═══════════════════════════════════════════════════════════════════════

class TestConceptSuggestions:
    def test_empty_query_returns_popular(self, test_client):
        """Empty query returns popular concept list."""
        resp = test_client.get("/api/search/concepts?q=")
        data = resp.json()
        assert len(data["concepts"]) > 0
        codes = {c["code"] for c in data["concepts"]}
        assert "price_to_earning" in codes  # pe
        assert "roe" in codes

    def test_prefix_match(self, test_client):
        """'pe' matches 'pe' alias (prefix match)."""
        resp = test_client.get("/api/search/concepts?q=pe")
        data = resp.json()
        assert any(c["code"] == "price_to_earning" for c in data["concepts"])

    def test_peg_suggestion(self, test_client):
        """'peg' suggestion returns peg_ratio."""
        resp = test_client.get("/api/search/concepts?q=peg")
        data = resp.json()
        assert any(c["code"] == "peg_ratio" for c in data["concepts"])

    def test_growth_suggestion(self, test_client):
        """'growth' matches profit/sales growth aliases."""
        resp = test_client.get("/api/search/concepts?q=growth")
        data = resp.json()
        codes = {c["code"] for c in data["concepts"]}
        assert "screener_profit_growth_3y" in codes or "screener_sales_growth_3y" in codes

    def test_no_duplicates(self, test_client):
        """Suggestions don't repeat the same concept_code."""
        resp = test_client.get("/api/search/concepts?q=p")
        data = resp.json()
        codes = [c["code"] for c in data["concepts"]]
        assert len(codes) == len(set(codes))

    def test_limit_respected(self, test_client):
        """Max 15 suggestions returned."""
        resp = test_client.get("/api/search/concepts?q=a")
        data = resp.json()
        assert len(data["concepts"]) <= 15
