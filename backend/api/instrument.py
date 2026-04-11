"""
Instrument API endpoints.

Price history and technical indicators for any instrument (stock, index, commodity, etc.).
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/instrument", tags=["instrument"])


@router.get("/{symbol}/price-history")
def price_history(
    symbol: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(365, ge=1, le=2000),
):
    """OHLCV price history for charting. Returns best-source prices."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        instrument = conn.execute(
            "SELECT instrument_id FROM instruments WHERE symbol = ? AND is_active = 1",
            (symbol.upper(),)
        ).fetchone()
        if not instrument:
            raise HTTPException(status_code=404, detail=f"Instrument '{symbol}' not found")

        sql = """
            SELECT trade_date, open, high, low, close, adj_close, volume, delivery_qty
            FROM best_prices
            WHERE instrument_id = ?
        """
        params: list = [instrument["instrument_id"]]

        if start_date:
            sql += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND trade_date <= ?"
            params.append(end_date)

        sql += " ORDER BY trade_date DESC LIMIT ?"
        params.append(limit)

        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        rows.reverse()  # Chronological order for charting

        elapsed = time.time() - t0
        logger.info("GET /api/instrument/%s/price-history — %d rows, %.3fs", symbol, len(rows), elapsed)
        return {"symbol": symbol.upper(), "prices": rows, "count": len(rows)}
    finally:
        conn.close()


@router.get("/{symbol}/technicals")
def instrument_technicals(
    symbol: str,
    date: Optional[str] = Query(None, description="As-of date; defaults to latest"),
):
    """Technical indicators for an instrument."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        instrument = conn.execute(
            "SELECT instrument_id FROM instruments WHERE symbol = ? AND is_active = 1",
            (symbol.upper(),)
        ).fetchone()
        if not instrument:
            raise HTTPException(status_code=404, detail=f"Instrument '{symbol}' not found")

        if date:
            rows = conn.execute("""
                SELECT indicator_code, value, trade_date
                FROM best_technicals
                WHERE instrument_id = ? AND trade_date = ?
            """, (instrument["instrument_id"], date)).fetchall()
        else:
            rows = conn.execute("""
                SELECT dt.indicator_code, dt.value, dt.trade_date
                FROM derived_technicals dt
                WHERE dt.instrument_id = ?
                  AND dt.trade_date = (
                      SELECT MAX(dt2.trade_date) FROM derived_technicals dt2
                      WHERE dt2.instrument_id = dt.instrument_id AND dt2.indicator_code = dt.indicator_code
                  )
            """, (instrument["instrument_id"],)).fetchall()

        result = {r["indicator_code"]: {"value": r["value"], "date": r["trade_date"]} for r in rows}
        elapsed = time.time() - t0
        logger.info("GET /api/instrument/%s/technicals — %d indicators, %.3fs", symbol, len(result), elapsed)
        return {"symbol": symbol.upper(), "technicals": result}
    finally:
        conn.close()
