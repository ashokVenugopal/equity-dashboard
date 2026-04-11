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
_CONCEPT_ALIASES = {
    "sales": "sales", "revenue": "sales",
    "net profit": "net_profit", "pat": "net_profit", "profit": "net_profit",
    "market cap": "market_cap", "mcap": "market_cap",
    "eps": "eps",
    "pe": "price_to_earning", "p/e": "price_to_earning",
    "roe": "roe", "roce": "roce",
    "npm": "npm", "opm": "opm",
    "debt": "debt_to_equity", "debt to equity": "debt_to_equity", "d/e": "debt_to_equity",
    "borrowings": "borrowings",
    "dividend yield": "dividend_yield", "dy": "dividend_yield",
    "current ratio": "current_ratio",
    "interest coverage": "interest_coverage",
    "promoter holding": "sh_promoters", "promoters": "sh_promoters",
    "fii holding": "sh_fiis", "fii": "sh_fiis",
    "dii holding": "sh_diis", "dii": "sh_diis",
    "sales growth": "sales_growth_headline", "pat growth": "profit_growth",
    "book value": "book_value",
    "price to book": "price_to_book", "p/b": "price_to_book",
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
                    conditions.append({"concept_code": concept_code, "op": sql_op, "value": value, "raw": part})
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
            cte_parts.append(f"""
                {alias} AS (
                    SELECT bf.company_id, bf.value AS {alias}_val
                    FROM best_facts_consolidated bf
                    JOIN concepts co ON bf.concept_id = co.concept_id
                    JOIN sources s ON bf.source_id = s.source_id
                    WHERE co.concept_code = '{cond["concept_code"]}'
                      AND s.period_type IN ('annual', 'snapshot')
                      AND bf.fact_id = (
                          SELECT bf2.fact_id FROM best_facts_consolidated bf2
                          JOIN concepts co2 ON bf2.concept_id = co2.concept_id
                          JOIN sources s2 ON bf2.source_id = s2.source_id
                          WHERE co2.concept_code = '{cond["concept_code"]}'
                            AND bf2.company_id = bf.company_id
                            AND s2.period_type IN ('annual', 'snapshot')
                          ORDER BY bf2.period_end_date DESC
                          LIMIT 1
                      )
                )
            """)
            where_parts.append(f"{alias}.{alias}_val {cond['op']} {cond['value']}")

        sql = f"""
            WITH {','.join(cte_parts)}
            SELECT comp.symbol, comp.name,
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
