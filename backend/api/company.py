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

        # Get classifications (deduped — version tracking creates multiple rows)
        classifications = conn.execute("""
            SELECT DISTINCT cl.classification_type, cl.classification_name
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
    grain: str = Query("annual", pattern="^(annual|quarterly|half_yearly)$",
                       description="Period grain for the columns"),
):
    """
    Financial data pivoted: concepts as rows, period_end_dates as columns.

    Columns are single-grain (annual | quarterly | half_yearly) — mixing
    grains interleaves annual columns with quarter-ends and screener
    snapshot dates, producing mostly-empty tables. A section with no data
    at the requested grain (e.g. cash flow is annual-only for most
    companies) falls back to annual; grain_used reports the per-section
    outcome and section_periods carries each section's own column list.
    """
    logger.info("GET /api/company/%s/financials — statement_type=%s, section=%s, grain=%s",
                symbol, statement_type, section, grain)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        company = conn.execute("SELECT company_id FROM companies WHERE symbol = ?", (symbol.upper(),)).fetchone()
        if not company:
            raise HTTPException(status_code=404, detail=f"Company '{symbol}' not found")

        view = "best_facts_consolidated" if statement_type == "consolidated" else "best_facts_consolidated"

        def _fetch(grain_value, only_section=None):
            section_filter = ""
            params = [company["company_id"], grain_value]
            if only_section:
                section_filter = "AND c.section = ?"
                params.append(only_section)
            elif section and section != "all":
                section_filter = "AND c.section = ?"
                params.append(section)
            return conn.execute(f"""
                SELECT bf.concept_code, bf.concept_name, c.section, c.unit,
                       bf.period_end_date, bf.value, bf.fiscal_year
                FROM {view} bf
                JOIN concepts c ON bf.concept_id = c.concept_id
                JOIN sources s ON bf.source_id = s.source_id
                WHERE bf.company_id = ?
                  AND s.period_type = ?
                  {section_filter}
                ORDER BY c.concept_id, bf.period_end_date DESC
            """, params).fetchall()

        rows = list(_fetch(grain))
        grain_used = {}

        # Which grains exist per section (for the frontend toggle)
        grains_available = {}
        for r in conn.execute(f"""
            SELECT DISTINCT c.section, s.period_type
            FROM {view} bf
            JOIN concepts c ON bf.concept_id = c.concept_id
            JOIN sources s ON bf.source_id = s.source_id
            WHERE bf.company_id = ? AND s.period_type != 'snapshot'
        """, (company["company_id"],)):
            grains_available.setdefault(r["section"], []).append(r["period_type"])

        # Sections that publish nothing at this grain fall back to annual
        if grain != "annual":
            present = {r["section"] for r in rows}
            for sec in ("profit_loss", "balance_sheet", "cash_flow"):
                if sec in present or "annual" not in grains_available.get(sec, []):
                    continue
                if section and section != "all" and section != sec:
                    continue
                rows.extend(_fetch("annual", only_section=sec))
                grain_used[sec] = "annual"

        # Pivot: group by section, then by concept; periods per section
        sections_data = {}
        periods_set = set()
        section_periods = {}
        for r in rows:
            sec = r["section"]
            code = r["concept_code"]
            period = r["period_end_date"]
            if period is not None:
                periods_set.add(period)
                section_periods.setdefault(sec, set()).add(period)

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
            "grain": grain,
            "grain_used": {sec: grain_used.get(sec, grain) for sec in sections_data},
            "grains_available": grains_available,
            "periods": periods,
            "section_periods": {sec: sorted(p, reverse=True)
                                for sec, p in section_periods.items()},
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


# ─────────────────────────────────────────────────────────────────────────
# Risk / Reward
# ─────────────────────────────────────────────────────────────────────────

def _fact_series(conn, company_id: int, concept_code: str, period_type: str,
                 limit: int = 60):
    """(period_end_date, value) ascending from best_facts_preferred."""
    rows = conn.execute("""
        SELECT bf.period_end_date, bf.value
        FROM best_facts_preferred bf
        WHERE bf.company_id = ? AND bf.concept_code = ?
          AND bf.period_type = ?
          AND (bf.fiscal_year IS NULL OR bf.fiscal_year != 'TTM')
          AND bf.value IS NOT NULL
        ORDER BY bf.period_end_date DESC
        LIMIT ?
    """, (company_id, concept_code, period_type, limit)).fetchall()
    return sorted((r["period_end_date"], r["value"]) for r in rows)


def _latest_fact(conn, company_id: int, concept_code: str,
                 period_type: str = "annual"):
    series = _fact_series(conn, company_id, concept_code, period_type, limit=1)
    return series[-1][1] if series else None


@router.get("/{symbol}/risk-reward")
def company_risk_reward(symbol: str):
    """Valuation altitude gauges + price-change attribution.

    - pe: daily PE (close / TTM EPS) over the last year — floor, peak,
      current altitude, and a downsampled trend for hover sparklines.
    - ev_ebitda: daily (mktcap + borrowings − cash) / TTM operating profit.
    - ocf_pat: annual CFO / PAT over the last 10 fiscal years (cash-flow
      statements are annual — a 1-year range does not exist for this).
    - attribution: price change over 1W/1M/3M/6M/1Y/3Y decomposed into
      earnings change vs multiple change (log-space shares).
    """
    from backend.core.risk_reward import (
        build_attribution_rows, build_ttm_series, daily_ratio_series,
        gauge_from_series,
    )

    logger.info("GET /api/company/%s/risk-reward", symbol)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        company = conn.execute(
            "SELECT company_id FROM companies WHERE symbol = ?",
            (symbol.upper(),)
        ).fetchone()
        if not company:
            raise HTTPException(status_code=404, detail=f"Company '{symbol}' not found")
        company_id = company["company_id"]

        instrument = conn.execute(
            "SELECT instrument_id FROM instruments "
            "WHERE symbol = ? AND instrument_type = 'stock' AND is_active = 1",
            (symbol.upper(),)
        ).fetchone()
        if not instrument:
            raise HTTPException(status_code=404, detail=f"No instrument for '{symbol}'")

        # 3Y attribution boundary (1095d) + its staleness tolerance (~110d)
        # must fit inside the fetch window.
        price_rows = conn.execute("""
            SELECT trade_date, close FROM best_prices
            WHERE instrument_id = ? AND trade_date >= date('now', '-1300 days')
            ORDER BY trade_date ASC
        """, (instrument["instrument_id"],)).fetchall()
        prices = [(r["trade_date"], r["close"]) for r in price_rows
                  if r["close"] is not None]
        if not prices:
            raise HTTPException(status_code=404, detail=f"No price data for '{symbol}'")
        prices_1y = prices[-252:]  # ~1 trading year

        # TTM EPS + TTM operating profit from quarterly facts
        eps_q = _fact_series(conn, company_id, "eps", "quarterly")
        ttm_eps = build_ttm_series(eps_q)
        op_q = _fact_series(conn, company_id, "operating_profit", "quarterly")
        ttm_ebitda = build_ttm_series(op_q)

        # PE gauge (1y)
        pe_series = daily_ratio_series(prices_1y, ttm_eps)
        pe_gauge = gauge_from_series(pe_series)

        # EV/EBITDA gauge (1y): EV = close×shares + borrowings − cash.
        # Shares are in count; close×shares gives INR — facts are in Cr,
        # so scale by 1e-7 (1 Cr = 1e7).
        ev_gauge = None
        shares = _latest_fact(conn, company_id, "num_equity_shares")
        borrowings = _latest_fact(conn, company_id, "borrowings") or 0.0
        cash = _latest_fact(conn, company_id, "cash_and_bank") or 0.0
        if shares and ttm_ebitda:
            ev_series = daily_ratio_series(
                prices_1y, ttm_ebitda,
                numerator_extra=(borrowings - cash),
                price_multiplier=shares * 1e-7,
            )
            ev_gauge = gauge_from_series(ev_series)

        # OCF/PAT gauge: annual, last 10 FYs
        cfo_a = dict(_fact_series(conn, company_id, "cfo", "annual", limit=14))
        pat_a = dict(_fact_series(conn, company_id, "net_profit", "annual", limit=14))
        ocf_pat_series = sorted(
            (d, round(cfo_a[d] / pat_a[d], 3))
            for d in (set(cfo_a) & set(pat_a))
            if pat_a[d] and pat_a[d] > 0
        )[-10:]
        ocf_gauge = gauge_from_series(ocf_pat_series)

        # Attribution table (annual EPS as 3Y fallback)
        eps_annual = _fact_series(conn, company_id, "eps", "annual", limit=8)
        attribution = build_attribution_rows(prices, ttm_eps, eps_annual)

        elapsed = time.time() - t0
        logger.info("GET /api/company/%s/risk-reward — %.3fs", symbol, elapsed)
        return {
            "symbol": symbol.upper(),
            "pe": pe_gauge,
            "ev_ebitda": ev_gauge,
            "ocf_pat": ocf_gauge,
            "attribution": attribution,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/company/%s/risk-reward — failed: %s", symbol, e)
        raise
    finally:
        conn.close()
