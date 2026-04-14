"""
Search API — company search and CLI filter parsing.

Level 1 deterministic parsing for Bloomberg-style command bar:
  - Navigation: "RELIANCE" → company page
  - Filter: "Filter: SME, PAT Growth > 20%, Debt < 0.5" → SQL query
"""
import logging
import re
import time
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

# ── Concept aliases for filter parsing ──
# Maps user-friendly names to concept_code in the database.
# Keep sorted by category for maintainability.
_CONCEPT_ALIASES = {
    # Revenue & Profit
    "sales": "sales", "revenue": "sales",
    "net profit": "net_profit", "pat": "net_profit", "profit": "net_profit",
    "operating profit": "operating_profit", "ebitda": "operating_profit",
    "eps": "eps", "earnings per share": "eps",
    # Market
    "market cap": "market_cap", "mcap": "market_cap", "market capitalisation": "market_cap",
    "current price": "current_price", "price": "current_price", "cmp": "current_price",
    # Valuation ratios
    "pe": "price_to_earning", "p/e": "price_to_earning", "price to earning": "price_to_earning",
    "peg": "peg_ratio", "peg ratio": "peg_ratio",
    "price to book": "price_to_book", "p/b": "price_to_book", "pb": "price_to_book",
    "price to sales": "price_to_sales", "p/s": "price_to_sales",
    "ev/ebitda": "ev_ebitda", "ev ebitda": "ev_ebitda",
    "dividend yield": "dividend_yield", "dy": "dividend_yield",
    "earnings yield": "earnings_yield",
    # Margins
    "npm": "npm", "net profit margin": "npm", "net margin": "npm",
    "opm": "opm", "operating margin": "opm", "operating profit margin": "opm",
    "gross margin": "gross_margin",
    # Returns
    "roe": "roe", "return on equity": "roe",
    "roce": "roce", "return on capital": "roce",
    "roic": "roic", "return on invested capital": "roic",
    "roa": "return_on_assets", "return on assets": "return_on_assets",
    # Leverage & coverage
    "debt": "debt_to_equity", "debt to equity": "debt_to_equity", "d/e": "debt_to_equity",
    "borrowings": "borrowings",
    "current ratio": "current_ratio",
    "quick ratio": "quick_ratio",
    "interest coverage": "interest_coverage",
    # Growth (mapped to screener concepts that have actual data)
    "sales growth": "screener_sales_growth_3y", "revenue growth": "screener_sales_growth_3y",
    "sales growth 3y": "screener_sales_growth_3y",
    "sales growth 5y": "screener_sales_growth_5y",
    "sales growth 10y": "screener_sales_growth_10y",
    "sales growth ttm": "screener_sales_growth_ttm",
    "profit growth": "screener_profit_growth_3y", "pat growth": "screener_profit_growth_3y",
    "earnings growth": "screener_profit_growth_3y",
    "profit growth 3y": "screener_profit_growth_3y",
    "profit growth 5y": "screener_profit_growth_5y",
    "profit growth 10y": "screener_profit_growth_10y",
    "profit growth ttm": "screener_profit_growth_ttm",
    # Balance sheet
    "book value": "book_value",
    "total assets": "total_assets",
    "total liabilities": "total_liabilities",
    "reserves": "reserves",
    "equity": "equity_share_capital",
    # Cash flow
    "cfo": "cfo", "cash from operations": "cfo",
    "free cash flow": "free_cash_flow", "fcf": "free_cash_flow",
    # Shareholding
    "promoter holding": "sh_promoters", "promoters": "sh_promoters", "promoter": "sh_promoters",
    "fii holding": "sh_fiis", "fii": "sh_fiis",
    "dii holding": "sh_diis", "dii": "sh_diis",
    "public holding": "sh_public", "public": "sh_public",
    # Turnover & efficiency
    "debtor days": "debtor_days",
    "inventory turnover": "inventory_turnover",
    "asset turnover": "asset_turnover",
    "fixed asset turnover": "fixed_asset_turnover", "fat": "fixed_asset_turnover",
    # Enterprise value
    "ev": "enterprise_value", "enterprise value": "enterprise_value",
    "ev/ebitda": "ev_ebitda", "ev ebitda": "ev_ebitda",
    # Cash flow ratios
    "price to fcf": "price_to_fcf", "p/fcf": "price_to_fcf",
    "fcf to sales": "fcf_to_sales", "fcf margin": "fcf_to_sales",
    # DuPont & payout
    "equity multiplier": "equity_multiplier",
    "dividend payout": "dividend_payout", "payout ratio": "dividend_payout",
    "adjusted eps": "adjusted_eps_ratio",
    # Margins
    "gross margin": "gross_margin",
}

# ── Filter condition regex ──
_CONDITION_RE = re.compile(
    r"(?P<concept>[a-zA-Z/\s]+?)\s*(?P<op>[><=!]+)\s*(?P<value>[\d.]+)",
    re.IGNORECASE,
)


@router.get("/companies")
def search_companies(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
):
    """Search companies by symbol, name, or ISIN."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        term = q.strip().upper()
        rows = conn.execute("""
            SELECT symbol, name, isin
            FROM companies
            WHERE symbol LIKE ? OR UPPER(name) LIKE ? OR isin LIKE ?
            ORDER BY
                CASE
                    WHEN symbol = ? THEN 1
                    WHEN symbol LIKE ? THEN 2
                    WHEN UPPER(name) LIKE ? THEN 3
                    ELSE 4
                END,
                symbol
            LIMIT ?
        """, (
            f"{term}%", f"%{term}%", f"{term}%",
            term, f"{term}%", f"%{term}%",
            limit,
        )).fetchall()

        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/search/companies?q=%s — %d results, %.3fs", q, len(result), elapsed)
        return {"query": q, "results": result, "count": len(result)}
    finally:
        conn.close()


class FilterRequest(BaseModel):
    expression: str
    limit: int = 50


@router.post("/filter")
def filter_companies(body: FilterRequest):
    """
    Parse and execute a filter expression.
    Format: "Filter: <tag>, <concept> <op> <value>, ..."
    Examples:
      - "Filter: PAT Growth > 20, Debt < 0.5"
      - "Filter: PE < 15, ROE > 20, Market Cap > 5000"
    """
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        expr = body.expression.strip()
        # Strip leading "Filter:" prefix
        if expr.lower().startswith("filter:"):
            expr = expr[7:].strip()

        parts = [p.strip() for p in expr.split(",") if p.strip()]
        conditions = []
        parse_errors = []

        for part in parts:
            match = _CONDITION_RE.match(part)
            if match:
                concept_raw = match.group("concept").strip().lower()
                op = match.group("op")
                value = float(match.group("value"))

                concept_code = _CONCEPT_ALIASES.get(concept_raw)
                if not concept_code:
                    # Try partial match
                    for alias, code in _CONCEPT_ALIASES.items():
                        if concept_raw in alias or alias in concept_raw:
                            concept_code = code
                            break

                if concept_code:
                    sql_op = {">=": ">=", "<=": "<=", ">": ">", "<": "<", "=": "=", "!=": "!="}.get(op, ">")
                    # Look up the concept's unit for frontend formatting
                    unit_row = conn.execute(
                        "SELECT unit FROM concepts WHERE concept_code = ?", (concept_code,)
                    ).fetchone()
                    unit = unit_row["unit"] if unit_row else None
                    conditions.append({"concept_code": concept_code, "op": sql_op, "value": value, "raw": part, "unit": unit})
                else:
                    parse_errors.append(f"Unknown concept: '{concept_raw}'")
            else:
                parse_errors.append(f"Could not parse: '{part}'")

        if not conditions:
            elapsed = time.time() - t0
            return {
                "expression": body.expression,
                "parsed_conditions": [],
                "parse_errors": parse_errors,
                "results": [],
                "count": 0,
                "elapsed_ms": round(elapsed * 1000, 1),
            }

        # Build SQL: for each condition, get latest annual best_fact and filter
        cte_parts = []
        where_parts = []
        for i, cond in enumerate(conditions):
            alias = f"c{i}"
            # Query facts directly (avoids slow best_facts_consolidated view)
            cte_parts.append(f"""
                {alias} AS (
                    SELECT f.company_id, f.value AS {alias}_val
                    FROM facts f
                    JOIN sources s ON f.source_id = s.source_id
                    JOIN concepts co ON f.concept_id = co.concept_id
                    WHERE co.concept_code = '{cond["concept_code"]}'
                      AND s.period_type IN ('annual', 'snapshot')
                      AND s.statement_type = 'consolidated'
                      AND f.fact_id = (
                          SELECT f2.fact_id FROM facts f2
                          JOIN sources s2 ON f2.source_id = s2.source_id
                          JOIN concepts co2 ON f2.concept_id = co2.concept_id
                          WHERE co2.concept_code = '{cond["concept_code"]}'
                            AND f2.company_id = f.company_id
                            AND s2.period_type IN ('annual', 'snapshot')
                            AND s2.statement_type = 'consolidated'
                          ORDER BY f2.period_end_date DESC,
                              CASE s2.derivation WHEN 'original' THEN 1 WHEN 'aggregated' THEN 2 ELSE 3 END,
                              CASE s2.file_type WHEN 'screener_excel' THEN 1 WHEN 'screener_web' THEN 2 ELSE 3 END,
                              f2.created_at DESC
                          LIMIT 1
                      )
                )
            """)
            where_parts.append(f"{alias}.{alias}_val {cond['op']} {cond['value']}")

        sql = f"""
            WITH {','.join(cte_parts)}
            SELECT comp.symbol, COALESCE(comp.name, comp.symbol) AS name,
                   {', '.join(f'{f"c{i}"}.{f"c{i}"}_val AS {conditions[i]["concept_code"]}' for i in range(len(conditions)))}
            FROM companies comp
            {' '.join(f'JOIN c{i} ON comp.company_id = c{i}.company_id' for i in range(len(conditions)))}
            WHERE {' AND '.join(where_parts)}
            ORDER BY comp.symbol
            LIMIT ?
        """

        rows = conn.execute(sql, (body.limit,)).fetchall()
        result = [dict(r) for r in rows]

        elapsed = time.time() - t0
        logger.info("POST /api/search/filter — %d conditions, %d results, %.3fs",
                     len(conditions), len(result), elapsed)
        return {
            "expression": body.expression,
            "parsed_conditions": conditions,
            "parse_errors": parse_errors,
            "results": result,
            "count": len(result),
            "elapsed_ms": round(elapsed * 1000, 1),
        }
    finally:
        conn.close()


@router.get("/suggestions")
def search_suggestions(q: str = Query("", description="Partial input")):
    """Autocomplete suggestions for the command bar."""
    t0 = time.time()
    suggestions = []

    term = q.strip().lower()
    if not term:
        suggestions = [
            {"type": "hint", "text": "Type a symbol (RELIANCE) or filter (Filter: PE < 15, ROE > 20)"},
        ]
    else:
        # Check if it looks like a filter
        if term.startswith("filter") or any(op in term for op in [">", "<", "="]):
            # Suggest concept names
            matching = [alias for alias in _CONCEPT_ALIASES if term.replace("filter:", "").strip() in alias]
            suggestions = [{"type": "concept", "text": a, "code": _CONCEPT_ALIASES[a]} for a in matching[:8]]
        else:
            # Suggest companies
            conn = get_pipeline_connection()
            try:
                rows = conn.execute("""
                    SELECT symbol, name FROM companies
                    WHERE symbol LIKE ? OR UPPER(name) LIKE ?
                    ORDER BY CASE WHEN symbol LIKE ? THEN 1 ELSE 2 END
                    LIMIT 8
                """, (f"{term.upper()}%", f"%{term.upper()}%", f"{term.upper()}%")).fetchall()
                suggestions = [{"type": "company", "text": f"{r['symbol']} — {r['name']}", "symbol": r["symbol"]} for r in rows]
            finally:
                conn.close()

    elapsed = time.time() - t0
    logger.info("GET /api/search/suggestions?q=%s — %d suggestions, %.3fs", q, len(suggestions), elapsed)
    return {"query": q, "suggestions": suggestions}


@router.get("/concepts")
def search_concepts(q: str = Query("", description="Partial concept name")):
    """
    Autocomplete for filter concepts. Returns matching concept aliases
    with their concept_code, grouped to avoid duplicates.
    """
    term = q.strip().lower()
    if not term:
        # Return popular/common concepts
        popular = [
            "pe", "peg", "roe", "roce", "npm", "opm", "debt",
            "market cap", "eps", "sales", "net profit", "dividend yield",
            "sales growth", "profit growth", "book value", "price to book",
            "current ratio", "interest coverage", "promoters", "fii",
        ]
        return {"concepts": [{"alias": a, "code": _CONCEPT_ALIASES[a]} for a in popular]}

    # Find matching aliases
    seen_codes: set = set()
    results = []
    # Exact prefix matches first
    for alias, code in _CONCEPT_ALIASES.items():
        if alias.startswith(term) and code not in seen_codes:
            results.append({"alias": alias, "code": code})
            seen_codes.add(code)
    # Then substring matches
    for alias, code in _CONCEPT_ALIASES.items():
        if term in alias and code not in seen_codes:
            results.append({"alias": alias, "code": code})
            seen_codes.add(code)

    return {"concepts": results[:15]}
