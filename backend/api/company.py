"""
Company API endpoints.

Screener.in-style company fundamentals: P&L, Balance Sheet, Cash Flow, ratios,
shareholding — all pivoted by period (concepts as rows, periods as columns).
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/company", tags=["company"])


@router.get("/{symbol}")
def company_meta(symbol: str):
    """Company metadata: name, ISIN, sector, FY end month."""
    logger.info("GET /api/company/%s", symbol)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        row = conn.execute("""
            SELECT c.company_id, c.symbol, c.name, c.isin, c.slug, c.fy_end_month
            FROM companies c WHERE c.symbol = ?
        """, (symbol.upper(),)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Company '{symbol}' not found")

        company_id = row["company_id"]

        # Get classifications (sector, theme, etc.)
        classifications = conn.execute("""
            SELECT cl.classification_type, cl.classification_name
            FROM classifications cl
            JOIN instruments i ON cl.instrument_id = i.instrument_id
            WHERE i.company_id = ?
              AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
            ORDER BY cl.classification_type, cl.classification_name
        """, (company_id,)).fetchall()

        result = dict(row)
        result["classifications"] = [dict(c) for c in classifications]

        elapsed = time.time() - t0
        logger.info("GET /api/company/%s — %.3fs", symbol, elapsed)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/company/%s — failed: %s", symbol, e)
        raise
    finally:
        conn.close()


@router.get("/{symbol}/financials")
def company_financials(
    symbol: str,
    statement_type: str = Query("consolidated", description="consolidated or standalone"),
    section: Optional[str] = Query(None, description="profit_loss, balance_sheet, cash_flow, or all"),
):
    """
    Financial data pivoted: concepts as rows, period_end_dates as columns.
    Returns structured JSON for screener.in-style table rendering.
    """
    logger.info("GET /api/company/%s/financials — statement_type=%s, section=%s", symbol, statement_type, section)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        company = conn.execute("SELECT company_id FROM companies WHERE symbol = ?", (symbol.upper(),)).fetchone()
        if not company:
            raise HTTPException(status_code=404, detail=f"Company '{symbol}' not found")

        view = "best_facts_consolidated" if statement_type == "consolidated" else "best_facts_consolidated"

        section_filter = ""
        params = [company["company_id"]]
        if section and section != "all":
            section_filter = "AND c.section = ?"
            params.append(section)

        rows = conn.execute(f"""
            SELECT bf.concept_code, bf.concept_name, c.section, c.unit,
                   bf.period_end_date, bf.value, bf.fiscal_year
            FROM {view} bf
            JOIN concepts c ON bf.concept_id = c.concept_id
            JOIN sources s ON bf.source_id = s.source_id
            WHERE bf.company_id = ?
              AND s.period_type = 'annual'
              {section_filter}
            ORDER BY c.section,
                     CASE c.section
                         WHEN 'profit_loss' THEN c.concept_id
                         WHEN 'balance_sheet' THEN c.concept_id
                         WHEN 'cash_flow' THEN c.concept_id
                         ELSE c.concept_id
                     END,
                     bf.period_end_date DESC
        """, params).fetchall()

        # Pivot: group by section, then by concept, with periods as columns
        sections_data = {}
        periods_set = set()
        for r in rows:
            sec = r["section"]
            code = r["concept_code"]
            period = r["period_end_date"]
            if period is not None:
                periods_set.add(period)

            if sec not in sections_data:
                sections_data[sec] = {}
            if code not in sections_data[sec]:
                sections_data[sec][code] = {
                    "concept_code": code,
                    "concept_name": r["concept_name"],
                    "unit": r["unit"],
                    "values": {},
                }
            sections_data[sec][code]["values"][period] = r["value"]

        periods = sorted(periods_set, reverse=True)

        result = {
            "symbol": symbol.upper(),
            "statement_type": statement_type,
            "periods": periods,
            "sections": {},
        }
        for sec_name, concepts in sections_data.items():
            result["sections"][sec_name] = list(concepts.values())

        elapsed = time.time() - t0
        logger.info("GET /api/company/%s/financials — %d concepts, %d periods, %.3fs",
                     symbol, sum(len(v) for v in sections_data.values()), len(periods), elapsed)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/company/%s/financials — failed: %s", symbol, e)
        raise
    finally:
        conn.close()


@router.get("/{symbol}/ratios")
def company_ratios(symbol: str):
    """Key ratios across annual periods."""
    logger.info("GET /api/company/%s/ratios", symbol)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        company = conn.execute("SELECT company_id FROM companies WHERE symbol = ?", (symbol.upper(),)).fetchone()
        if not company:
            raise HTTPException(status_code=404, detail=f"Company '{symbol}' not found")

        rows = conn.execute("""
            SELECT bf.concept_code, bf.concept_name, bf.period_end_date, bf.value
            FROM best_facts_consolidated bf
            JOIN concepts c ON bf.concept_id = c.concept_id
            JOIN sources s ON bf.source_id = s.source_id
            WHERE bf.company_id = ?
              AND c.section = 'ratio'
              AND s.period_type = 'annual'
            ORDER BY c.concept_id, bf.period_end_date DESC
        """, (company["company_id"],)).fetchall()

        ratios = {}
        periods_set = set()
        for r in rows:
            code = r["concept_code"]
            if r["period_end_date"] is not None:
                periods_set.add(r["period_end_date"])
            if code not in ratios:
                ratios[code] = {"concept_code": code, "concept_name": r["concept_name"], "values": {}}
            ratios[code]["values"][r["period_end_date"]] = r["value"]

        elapsed = time.time() - t0
        logger.info("GET /api/company/%s/ratios — %d ratios, %.3fs", symbol, len(ratios), elapsed)
        return {
            "symbol": symbol.upper(),
            "periods": sorted(periods_set, reverse=True),
            "ratios": list(ratios.values()),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/company/%s/ratios — failed: %s", symbol, e)
        raise
    finally:
        conn.close()


@router.get("/{symbol}/shareholding")
def company_shareholding(symbol: str):
    """Shareholding pattern (sh_* concepts) across periods."""
    logger.info("GET /api/company/%s/shareholding", symbol)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        company = conn.execute("SELECT company_id FROM companies WHERE symbol = ?", (symbol.upper(),)).fetchone()
        if not company:
            raise HTTPException(status_code=404, detail=f"Company '{symbol}' not found")

        rows = conn.execute("""
            SELECT bf.concept_code, bf.concept_name, bf.period_end_date, bf.value
            FROM best_facts_consolidated bf
            JOIN concepts c ON bf.concept_id = c.concept_id
            JOIN sources s ON bf.source_id = s.source_id
            WHERE bf.company_id = ?
              AND c.concept_code LIKE 'sh_%'
              AND s.period_type IN ('annual', 'snapshot')
            ORDER BY c.concept_id, bf.period_end_date DESC
        """, (company["company_id"],)).fetchall()

        holdings = {}
        periods_set = set()
        for r in rows:
            code = r["concept_code"]
            if r["period_end_date"] is not None:
                periods_set.add(r["period_end_date"])
            if code not in holdings:
                holdings[code] = {"concept_code": code, "concept_name": r["concept_name"], "values": {}}
            holdings[code]["values"][r["period_end_date"]] = r["value"]

        elapsed = time.time() - t0
        logger.info("GET /api/company/%s/shareholding — %d items, %.3fs", symbol, len(holdings), elapsed)
        return {
            "symbol": symbol.upper(),
            "periods": sorted(periods_set, reverse=True),
            "shareholding": list(holdings.values()),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/company/%s/shareholding — failed: %s", symbol, e)
        raise
    finally:
        conn.close()


@router.get("/{symbol}/peers")
def company_peers(symbol: str, limit: int = Query(10, ge=1, le=30)):
    """Companies in the same sector."""
    logger.info("GET /api/company/%s/peers — limit=%d", symbol, limit)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        # Find the sector for this company
        sector = conn.execute("""
            SELECT cl.classification_name
            FROM classifications cl
            JOIN instruments i ON cl.instrument_id = i.instrument_id
            JOIN companies c ON i.company_id = c.company_id
            WHERE c.symbol = ?
              AND cl.classification_type = 'sector'
              AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
            LIMIT 1
        """, (symbol.upper(),)).fetchone()

        if not sector:
            return {"symbol": symbol.upper(), "sector": None, "peers": []}

        rows = conn.execute("""
            SELECT c.symbol, c.name
            FROM classifications cl
            JOIN instruments i ON cl.instrument_id = i.instrument_id
            JOIN companies c ON i.company_id = c.company_id
            WHERE cl.classification_type = 'sector'
              AND cl.classification_name = ?
              AND c.symbol != ?
              AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
            ORDER BY c.symbol
            LIMIT ?
        """, (sector["classification_name"], symbol.upper(), limit)).fetchall()

        elapsed = time.time() - t0
        logger.info("GET /api/company/%s/peers — %d peers, %.3fs", symbol, len(rows), elapsed)
        return {
            "symbol": symbol.upper(),
            "sector": sector["classification_name"],
            "peers": [dict(r) for r in rows],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/company/%s/peers — failed: %s", symbol, e)
        raise
    finally:
        conn.close()
