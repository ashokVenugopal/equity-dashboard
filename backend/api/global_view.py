"""
Global view API endpoints.

Categorized views: global indices, commodities, forex, ADRs, bonds.
Built on top of the existing /api/market/global but with grouping.
"""
import logging
import time

from fastapi import APIRouter, HTTPException

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/global", tags=["global"])


@router.get("/overview")
def global_overview():
    """All non-stock instruments grouped by type with latest prices."""
    logger.info("GET /api/global/overview")
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            WITH lp AS (
                SELECT ph.instrument_id, ph.close, ph.trade_date, ph.open, ph.high, ph.low, ph.volume,
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
            ORDER BY i.instrument_type, i.symbol
        """).fetchall()

        grouped = {}
        for r in rows:
            t = r["instrument_type"]
            if t not in grouped:
                grouped[t] = []
            grouped[t].append(dict(r))

        elapsed = time.time() - t0
        logger.info("GET /api/global/overview — %d instruments, %.3fs", len(rows), elapsed)
        return {"groups": grouped, "total": len(rows)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/global/overview — failed: %s", e)
        raise
    finally:
        conn.close()


@router.get("/indices")
def global_indices():
    """Global indices only."""
    logger.info("GET /api/global/indices")
    return _get_by_type("index")


@router.get("/commodities")
def global_commodities():
    """Commodities only."""
    logger.info("GET /api/global/commodities")
    return _get_by_type("commodity")


@router.get("/forex")
def global_forex():
    """Forex pairs only."""
    logger.info("GET /api/global/forex")
    return _get_by_type("forex")


@router.get("/adrs")
def global_adrs():
    """ADRs only."""
    logger.info("GET /api/global/adrs")
    return _get_by_type("adr")


def _get_by_type(instrument_type: str):
    """Fetch instruments of a specific type with latest prices."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            WITH lp AS (
                SELECT ph.instrument_id, ph.close, ph.trade_date, ph.open, ph.high, ph.low, ph.volume,
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
                    SELECT instrument_id FROM instruments WHERE instrument_type = ? AND is_active = 1
                )
                  AND CAST(strftime('%w', ph.trade_date) AS INTEGER) NOT IN (0, 6)
            )
            SELECT i.symbol, i.name, i.currency,
                   lp.close, lp.trade_date, lp.open, lp.high, lp.low, lp.volume
            FROM instruments i
            LEFT JOIN lp ON lp.instrument_id = i.instrument_id AND lp.rn = 1
            WHERE i.instrument_type = ? AND i.is_active = 1
            ORDER BY i.symbol
        """, (instrument_type, instrument_type)).fetchall()

        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/global/%s — %d instruments, %.3fs", instrument_type, len(result), elapsed)
        return {"instrument_type": instrument_type, "instruments": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/global/%s — failed: %s", instrument_type, e)
        raise
    finally:
        conn.close()
