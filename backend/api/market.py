"""
Market Overview API endpoints.

Provides index cards, FII/DII flows, market breadth, and global instrument prices.
All data sourced via equity-shared views (best_prices, best_institutional_flows, market_breadth).
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/overview")
def market_overview():
    """
    Market overview: latest price + change for key indices, plus FII/DII summary and breadth.
    Returns a combined payload for the home page.
    """
    logger.info("GET /api/market/overview — fetching indices, flows, breadth...")
    t0 = time.time()
    errors = []
    conn = get_pipeline_connection()
    try:
        try:
            indices = _get_index_cards(conn)
        except Exception as e:
            logger.error("Failed to fetch index cards: %s", e)
            indices = []
            errors.append("index_cards")

        try:
            flows = _get_latest_flows(conn)
        except Exception as e:
            logger.error("Failed to fetch latest flows: %s", e)
            flows = []
            errors.append("flows")

        try:
            breadth = _get_latest_breadth(conn)
        except Exception as e:
            logger.error("Failed to fetch market breadth: %s", e)
            breadth = None
            errors.append("breadth")

        elapsed = time.time() - t0
        logger.info(
            "GET /api/market/overview — %d indices, %d flows, breadth=%s, %d errors, %.3fs%s",
            len(indices), len(flows), "yes" if breadth else "no",
            len(errors), elapsed,
            f" [failed: {', '.join(errors)}]" if errors else "",
        )
        return {"indices": indices, "flows": flows, "breadth": breadth}
    finally:
        conn.close()


@router.get("/flows")
def market_flows(
    participant_type: Optional[str] = Query(None, description="FII, DII, or MF"),
    period_type: str = Query("daily", description="daily, monthly, or yearly"),
    limit: int = Query(10, ge=1, le=100),
):
    """Latest institutional flows."""
    logger.info("GET /api/market/flows — participant=%s, period=%s, limit=%d...",
                participant_type or "all", period_type, limit)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = _query_flows(conn, participant_type, period_type, limit)
        elapsed = time.time() - t0
        logger.info("GET /api/market/flows — %d rows returned, %.3fs", len(rows), elapsed)
        return {"flows": rows}
    except Exception as e:
        logger.error("GET /api/market/flows — failed: %s", e)
        raise
    finally:
        conn.close()


@router.get("/flows/history")
def market_flows_history(
    participant_type: Optional[str] = Query(None),
    segment: str = Query("CASH", description="CASH, CASH_EQUITY, FO_INDEX_FUTURES, etc."),
    period_type: str = Query("daily"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(60, ge=1, le=365),
):
    """Flow time series for charting."""
    logger.info("GET /api/market/flows/history — segment=%s, period=%s, range=%s..%s...",
                segment, period_type, start_date or "earliest", end_date or "latest")
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        sql = """
            SELECT flow_date, participant_type, segment,
                   buy_value, sell_value, net_value
            FROM best_institutional_flows
            WHERE period_type = ?
              AND segment = ?
        """
        params = [period_type, segment]
        if participant_type:
            sql += " AND participant_type = ?"
            params.append(participant_type)
        if start_date:
            sql += " AND flow_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND flow_date <= ?"
            params.append(end_date)
        sql += " ORDER BY flow_date DESC LIMIT ?"
        params.append(limit)

        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        elapsed = time.time() - t0
        logger.info("GET /api/market/flows/history — %d rows, %.3fs", len(rows), elapsed)
        return {"flows": rows}
    except Exception as e:
        logger.error("GET /api/market/flows/history — failed: %s", e)
        raise
    finally:
        conn.close()


@router.get("/breadth")
def market_breadth(limit: int = Query(10, ge=1, le=60)):
    """Recent market breadth data (advances, declines, 52w highs/lows)."""
    logger.info("GET /api/market/breadth — limit=%d...", limit)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            SELECT trade_date, exchange, advances, declines, unchanged,
                   advance_decline_ratio, new_52w_highs, new_52w_lows,
                   total_traded, avg_delivery_pct
            FROM market_breadth
            WHERE (advances + declines) > 0
            ORDER BY trade_date DESC
            LIMIT ?
        """, (limit,)).fetchall()
        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/market/breadth — %d rows, %.3fs", len(result), elapsed)
        return {"breadth": result}
    except Exception as e:
        logger.error("GET /api/market/breadth — failed: %s", e)
        raise
    finally:
        conn.close()


@router.get("/global")
def market_global():
    """Latest prices for global indices, commodities, forex, bonds, crypto, ADRs."""
    logger.info("GET /api/market/global — fetching non-stock instruments...")
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        # Query price_history directly with window function (avoids slow best_prices view)
        rows = conn.execute("""
            WITH lp AS (
                SELECT ph.instrument_id, ph.trade_date, ph.open, ph.high, ph.low, ph.close, ph.volume,
                       ROW_NUMBER() OVER (
                           PARTITION BY ph.instrument_id
                           ORDER BY ph.trade_date DESC,
                               CASE ph.source
                                   WHEN 'nse_bhavcopy' THEN 1 WHEN 'bse_bhavcopy' THEN 2
                                   WHEN 'nse_index' THEN 3 WHEN 'yahoo_finance' THEN 4 ELSE 5
                               END
                       ) AS rn
                FROM price_history ph
                WHERE ph.instrument_id IN (
                    SELECT instrument_id FROM instruments WHERE instrument_type != 'stock' AND is_active = 1
                )
                  AND CAST(strftime('%w', ph.trade_date) AS INTEGER) NOT IN (0, 6)
            )
            SELECT i.instrument_type, i.symbol, i.name, i.currency,
                   lp.close, lp.trade_date, lp.open, lp.high, lp.low, lp.volume
            FROM instruments i
            LEFT JOIN lp ON lp.instrument_id = i.instrument_id AND lp.rn = 1
            WHERE i.instrument_type != 'stock' AND i.is_active = 1
            ORDER BY
                CASE i.instrument_type
                    WHEN 'index' THEN 1 WHEN 'commodity' THEN 2
                    WHEN 'forex' THEN 3 WHEN 'bond' THEN 4
                    WHEN 'crypto' THEN 5 WHEN 'adr' THEN 6 ELSE 7
                END,
                i.symbol
        """).fetchall()
        result = [dict(r) for r in rows]
        without_price = [r["symbol"] for r in result if r["close"] is None]
        elapsed = time.time() - t0
        logger.info(
            "GET /api/market/global — %d instruments (%d without prices), %.3fs%s",
            len(result), len(without_price), elapsed,
            f" [no price: {', '.join(without_price[:20])}]" if without_price else "",
        )
        return {"instruments": result}
    except Exception as e:
        logger.error("GET /api/market/global — failed: %s", e)
        raise
    finally:
        conn.close()


def _get_index_cards(conn):
    """Get latest price + previous day for change calculation for Indian indices."""
    # Query price_history directly — avoids the slow best_prices correlated subquery
    # Two-stage: first pick best source per date, then rank by date
    rows = conn.execute("""
        WITH best_per_date AS (
            SELECT ph.instrument_id, ph.trade_date, ph.open, ph.high, ph.low,
                   ph.close, ph.volume,
                   ROW_NUMBER() OVER (
                       PARTITION BY ph.instrument_id, ph.trade_date
                       ORDER BY CASE ph.source
                           WHEN 'nse_index' THEN 1 WHEN 'nse_bhavcopy' THEN 2
                           WHEN 'yahoo_finance' THEN 3 ELSE 4
                       END
                   ) AS src_rn
            FROM price_history ph
            WHERE ph.instrument_id IN (
                SELECT instrument_id FROM instruments
                WHERE instrument_type = 'index' AND exchange = 'NSE' AND is_active = 1
            )
              AND ph.trade_date IN (SELECT DISTINCT trade_date FROM market_breadth WHERE (advances + declines) > 0 ORDER BY trade_date DESC LIMIT 10)
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY trade_date DESC) AS rn
            FROM best_per_date WHERE src_rn = 1
        ),
        latest AS (
            SELECT * FROM ranked WHERE rn = 1
        ),
        prev AS (
            SELECT * FROM ranked WHERE rn = 2
        )
        SELECT i.symbol, i.name,
               lp.close, lp.trade_date, lp.open, lp.high, lp.low, lp.volume,
               pv.close AS prev_close, pv.trade_date AS prev_date,
               CASE WHEN pv.close > 0
                    THEN ROUND((lp.close - pv.close), 2)
                    ELSE NULL END AS change,
               CASE WHEN pv.close > 0
                    THEN ROUND((lp.close - pv.close) / pv.close * 100, 2)
                    ELSE NULL END AS change_pct
        FROM instruments i
        JOIN latest lp ON i.instrument_id = lp.instrument_id
        LEFT JOIN prev pv ON i.instrument_id = pv.instrument_id
        ORDER BY
            CASE i.symbol
                WHEN 'NIFTY50' THEN 1
                WHEN 'BANKNIFTY' THEN 2
                WHEN 'NIFTYNXT50' THEN 3
                WHEN 'NIFTYIT' THEN 4
                ELSE 10
            END,
            i.symbol
    """).fetchall()
    return [dict(r) for r in rows]


def _get_latest_flows(conn):
    """Get most recent FII and DII daily cash flows."""
    rows = conn.execute("""
        SELECT participant_type, segment, flow_date,
               buy_value, sell_value, net_value
        FROM best_institutional_flows
        WHERE period_type = 'daily'
          AND segment = 'CASH'
          AND flow_date = (
              SELECT MAX(flow_date)
              FROM best_institutional_flows
              WHERE period_type = 'daily' AND segment = 'CASH'
          )
        ORDER BY participant_type
    """).fetchall()
    return [dict(r) for r in rows]


def _get_latest_breadth(conn):
    """Get most recent market breadth."""
    row = conn.execute("""
        SELECT trade_date, advances, declines, unchanged,
               advance_decline_ratio, new_52w_highs, new_52w_lows
        FROM market_breadth
        WHERE (advances + declines) > 0
        ORDER BY trade_date DESC
        LIMIT 1
    """).fetchone()
    return dict(row) if row else None


def _query_flows(conn, participant_type, period_type, limit):
    """Query institutional flows with optional filters."""
    sql = """
        SELECT flow_date, participant_type, segment,
               buy_value, sell_value, net_value
        FROM best_institutional_flows
        WHERE period_type = ?
    """
    params = [period_type]
    if participant_type:
        sql += " AND participant_type = ?"
        params.append(participant_type)
    sql += " ORDER BY flow_date DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]
