"""
Derivatives API endpoints.

Put-Call Ratio, FII positioning, Open Interest changes, participant data.
Data sourced from fo_participant_positioning, options_chain_snapshot, fo_series_oi tables.
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, Query

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/derivatives", tags=["derivatives"])


@router.get("/pcr")
def put_call_ratio(
    instrument: str = Query("NIFTY", description="NIFTY or BANKNIFTY"),
    limit: int = Query(10, ge=1, le=60),
):
    """Put-Call Ratio derived from options chain data."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            SELECT instrument_symbol, trade_date, expiry_date,
                   SUM(CASE WHEN option_type = 'PE' THEN open_interest ELSE 0 END) AS put_oi,
                   SUM(CASE WHEN option_type = 'CE' THEN open_interest ELSE 0 END) AS call_oi,
                   CASE WHEN SUM(CASE WHEN option_type = 'CE' THEN open_interest ELSE 0 END) > 0
                        THEN ROUND(
                            CAST(SUM(CASE WHEN option_type = 'PE' THEN open_interest ELSE 0 END) AS REAL) /
                            SUM(CASE WHEN option_type = 'CE' THEN open_interest ELSE 0 END), 4)
                        ELSE NULL END AS pcr
            FROM options_chain_snapshot
            WHERE instrument_symbol = ?
            GROUP BY instrument_symbol, trade_date, expiry_date
            ORDER BY trade_date DESC, expiry_date ASC
            LIMIT ?
        """, (instrument.upper(), limit)).fetchall()

        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/derivatives/pcr — %d rows, %.3fs", len(result), elapsed)
        return {"instrument": instrument.upper(), "pcr_data": result}
    finally:
        conn.close()


@router.get("/fii-positioning")
def fii_positioning(limit: int = Query(10, ge=1, le=60)):
    """FII long/short positioning across index futures, index options, stock futures, stock options."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            SELECT trade_date, participant_type, instrument_category,
                   long_contracts, short_contracts, long_value, short_value,
                   CASE WHEN (long_contracts + short_contracts) > 0
                        THEN ROUND(CAST(long_contracts AS REAL) / (long_contracts + short_contracts) * 100, 2)
                        ELSE NULL END AS long_pct,
                   CASE WHEN (long_contracts + short_contracts) > 0
                        THEN ROUND(CAST(short_contracts AS REAL) / (long_contracts + short_contracts) * 100, 2)
                        ELSE NULL END AS short_pct
            FROM best_fo_participant_positioning
            WHERE participant_type = 'FII'
            ORDER BY trade_date DESC, instrument_category
            LIMIT ?
        """, (limit,)).fetchall()

        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/derivatives/fii-positioning — %d rows, %.3fs", len(result), elapsed)
        return {"positioning": result}
    finally:
        conn.close()


@router.get("/oi-changes")
def oi_changes(
    instrument: str = Query("NIFTY", description="NIFTY or BANKNIFTY"),
    limit: int = Query(10, ge=1, le=60),
):
    """Series-level OI changes (futures + options) with day-over-day percentage."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            SELECT instrument_symbol, trade_date, expiry_date,
                   futures_oi, options_oi, total_oi, total_volume
            FROM fo_series_oi
            WHERE instrument_symbol = ?
            ORDER BY trade_date DESC, expiry_date ASC
            LIMIT ?
        """, (instrument.upper(), limit)).fetchall()

        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/derivatives/oi-changes — %d rows, %.3fs", len(result), elapsed)
        return {"instrument": instrument.upper(), "oi_data": result}
    finally:
        conn.close()


@router.get("/participant/{date}")
def participant_positioning(date: str):
    """All participant positioning for a given date (FII, DII, CLIENT, PRO)."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            SELECT trade_date, participant_type, instrument_category,
                   long_contracts, short_contracts, long_value, short_value
            FROM best_fo_participant_positioning
            WHERE trade_date = ?
            ORDER BY participant_type, instrument_category
        """, (date,)).fetchall()

        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/derivatives/participant/%s — %d rows, %.3fs", date, len(result), elapsed)
        return {"date": date, "positioning": result}
    finally:
        conn.close()
