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
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        indices = _get_index_cards(conn)
        flows = _get_latest_flows(conn)
        breadth = _get_latest_breadth(conn)
        elapsed = time.time() - t0
        logger.info("GET /api/market/overview — %d indices, %.3fs", len(indices), elapsed)
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
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = _query_flows(conn, participant_type, period_type, limit)
        elapsed = time.time() - t0
        logger.info("GET /api/market/flows — %d rows, %.3fs", len(rows), elapsed)
        return {"flows": rows}
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
    finally:
        conn.close()


@router.get("/breadth")
def market_breadth(limit: int = Query(10, ge=1, le=60)):
    """Recent market breadth data (advances, declines, 52w highs/lows)."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            SELECT trade_date, exchange, advances, declines, unchanged,
                   advance_decline_ratio, new_52w_highs, new_52w_lows,
                   total_traded, avg_delivery_pct
            FROM market_breadth
            ORDER BY trade_date DESC
            LIMIT ?
        """, (limit,)).fetchall()
        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/market/breadth — %d rows, %.3fs", len(result), elapsed)
        return {"breadth": result}
    finally:
        conn.close()


@router.get("/global")
def market_global():
    """Latest prices for global indices, commodities, forex, bonds, crypto, ADRs."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            SELECT i.instrument_type, i.symbol, i.name, i.currency,
                   bp.close, bp.trade_date,
                   bp.open, bp.high, bp.low, bp.volume
            FROM instruments i
            LEFT JOIN (
                SELECT instrument_id, close, trade_date, open, high, low, volume,
                       ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY trade_date DESC) AS rn
                FROM best_prices
            ) bp ON bp.instrument_id = i.instrument_id AND bp.rn = 1
            WHERE i.instrument_type != 'stock'
              AND i.is_active = 1
            ORDER BY
                CASE i.instrument_type
                    WHEN 'index' THEN 1
                    WHEN 'commodity' THEN 2
                    WHEN 'forex' THEN 3
                    WHEN 'bond' THEN 4
                    WHEN 'crypto' THEN 5
                    WHEN 'adr' THEN 6
                    ELSE 7
                END,
                i.symbol
        """).fetchall()
        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/market/global — %d instruments, %.3fs", len(result), elapsed)
        return {"instruments": result}
    finally:
        conn.close()


def _get_index_cards(conn):
    """Get latest price + previous day for change calculation for Indian indices."""
    rows = conn.execute("""
        WITH latest AS (
            SELECT instrument_id,
                   MAX(trade_date) AS latest_date
            FROM best_prices
            WHERE instrument_id IN (
                SELECT instrument_id FROM instruments
                WHERE instrument_type = 'index' AND exchange = 'NSE' AND is_active = 1
            )
            GROUP BY instrument_id
        ),
        latest_prices AS (
            SELECT bp.instrument_id, bp.close, bp.trade_date, bp.open, bp.high, bp.low, bp.volume
            FROM best_prices bp
            JOIN latest l ON bp.instrument_id = l.instrument_id AND bp.trade_date = l.latest_date
        ),
        prev AS (
            SELECT bp.instrument_id, bp.close AS prev_close, bp.trade_date AS prev_date
            FROM best_prices bp
            JOIN latest l ON bp.instrument_id = l.instrument_id
            WHERE bp.trade_date < l.latest_date
            AND bp.trade_date >= date(l.latest_date, '-7 days')
            ORDER BY bp.trade_date DESC
        ),
        prev_dedup AS (
            SELECT instrument_id, prev_close, prev_date,
                   ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY prev_date DESC) AS rn
            FROM prev
        )
        SELECT i.symbol, i.name,
               lp.close, lp.trade_date, lp.open, lp.high, lp.low, lp.volume,
               pd.prev_close, pd.prev_date,
               CASE WHEN pd.prev_close > 0
                    THEN ROUND((lp.close - pd.prev_close), 2)
                    ELSE NULL END AS change,
               CASE WHEN pd.prev_close > 0
                    THEN ROUND((lp.close - pd.prev_close) / pd.prev_close * 100, 2)
                    ELSE NULL END AS change_pct
        FROM instruments i
        JOIN latest_prices lp ON i.instrument_id = lp.instrument_id
        LEFT JOIN prev_dedup pd ON i.instrument_id = pd.instrument_id AND pd.rn = 1
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
