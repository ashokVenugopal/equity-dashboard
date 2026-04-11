"""
Index deep-dive API endpoints.

Provides constituent lists, technicals, and movers for NIFTY/BANKNIFTY/etc.
Data sourced via equity-shared views and classifications.
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/index", tags=["index"])

# Map URL slugs to classification names
_INDEX_SLUG_MAP = {
    "nifty-50": "NIFTY 50",
    "nifty-bank": "NIFTY Bank",
    "nifty-next-50": "NIFTY Next 50",
    "nifty-it": "NIFTY IT",
    "nifty-auto": "Nifty Auto",
    "nifty-energy": "NIFTY Energy",
    "nifty-psu-bank": "Nifty PSU Bank",
    "nifty-100": "NIFTY 100",
    "nifty-200": "NIFTY 200",
    "nifty-500": "NIFTY 500",
}


def _resolve_index_name(slug: str) -> str:
    """Resolve URL slug to classification_name, or use as-is."""
    return _INDEX_SLUG_MAP.get(slug.lower(), slug)


@router.get("/{name}/constituents")
def index_constituents(name: str):
    """
    Get constituent stocks for an index with latest price, change, and key metrics.
    """
    logger.info("GET /api/index/%s/constituents", name)
    t0 = time.time()
    index_name = _resolve_index_name(name)
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            WITH constituents AS (
                SELECT i.instrument_id, i.symbol, i.name, i.company_id, cl.sort_order
                FROM classifications cl
                JOIN instruments i ON cl.instrument_id = i.instrument_id
                WHERE cl.classification_type = 'index_constituent'
                  AND cl.classification_name = ?
                  AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
                  AND i.is_active = 1
            ),
            latest_date AS (
                SELECT c.instrument_id, MAX(bp.trade_date) AS latest_date
                FROM constituents c
                JOIN best_prices bp ON bp.instrument_id = c.instrument_id
                GROUP BY c.instrument_id
            ),
            latest_prices AS (
                SELECT bp.instrument_id, bp.close, bp.open, bp.high, bp.low,
                       bp.volume, bp.trade_date
                FROM best_prices bp
                JOIN latest_date ld ON bp.instrument_id = ld.instrument_id
                  AND bp.trade_date = ld.latest_date
            ),
            prev_prices AS (
                SELECT bp.instrument_id, bp.close AS prev_close,
                       ROW_NUMBER() OVER (PARTITION BY bp.instrument_id ORDER BY bp.trade_date DESC) AS rn
                FROM best_prices bp
                JOIN latest_date ld ON bp.instrument_id = ld.instrument_id
                WHERE bp.trade_date < ld.latest_date
                  AND bp.trade_date >= date(ld.latest_date, '-7 days')
            )
            SELECT c.symbol, c.name, c.sort_order,
                   lp.close, lp.open, lp.high, lp.low, lp.volume, lp.trade_date,
                   pp.prev_close,
                   CASE WHEN pp.prev_close > 0
                        THEN ROUND(lp.close - pp.prev_close, 2)
                        ELSE NULL END AS change,
                   CASE WHEN pp.prev_close > 0
                        THEN ROUND((lp.close - pp.prev_close) / pp.prev_close * 100, 2)
                        ELSE NULL END AS change_pct
            FROM constituents c
            LEFT JOIN latest_prices lp ON c.instrument_id = lp.instrument_id
            LEFT JOIN prev_prices pp ON c.instrument_id = pp.instrument_id AND pp.rn = 1
            ORDER BY c.sort_order, c.symbol
        """, (index_name,)).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail=f"Index '{index_name}' not found or has no constituents")

        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/index/%s/constituents — %d stocks, %.3fs", name, len(result), elapsed)
        return {"index_name": index_name, "constituents": result, "count": len(result)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/index/%s/constituents — failed: %s", name, e)
        raise
    finally:
        conn.close()


@router.get("/{name}/movers")
def index_movers(name: str, limit: int = Query(5, ge=1, le=20)):
    """Top and bottom movers by daily change percentage."""
    logger.info("GET /api/index/%s/movers — limit=%d", name, limit)
    t0 = time.time()
    index_name = _resolve_index_name(name)
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            WITH constituents AS (
                SELECT i.instrument_id, i.symbol, i.name
                FROM classifications cl
                JOIN instruments i ON cl.instrument_id = i.instrument_id
                WHERE cl.classification_type = 'index_constituent'
                  AND cl.classification_name = ?
                  AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
            ),
            latest_date AS (
                SELECT c.instrument_id, MAX(bp.trade_date) AS latest_date
                FROM constituents c
                JOIN best_prices bp ON bp.instrument_id = c.instrument_id
                GROUP BY c.instrument_id
            ),
            with_change AS (
                SELECT c.symbol, c.name, bp.close, bp.trade_date,
                       prev.close AS prev_close,
                       CASE WHEN prev.close > 0
                            THEN ROUND((bp.close - prev.close) / prev.close * 100, 2)
                            ELSE NULL END AS change_pct
                FROM constituents c
                JOIN latest_date ld ON c.instrument_id = ld.instrument_id
                JOIN best_prices bp ON bp.instrument_id = c.instrument_id AND bp.trade_date = ld.latest_date
                LEFT JOIN (
                    SELECT bp2.instrument_id, bp2.close,
                           ROW_NUMBER() OVER (PARTITION BY bp2.instrument_id ORDER BY bp2.trade_date DESC) AS rn
                    FROM best_prices bp2
                    JOIN latest_date ld2 ON bp2.instrument_id = ld2.instrument_id
                    WHERE bp2.trade_date < ld2.latest_date
                ) prev ON prev.instrument_id = c.instrument_id AND prev.rn = 1
                WHERE change_pct IS NOT NULL
            )
            SELECT * FROM (
                SELECT *, 'gainer' AS mover_type FROM with_change ORDER BY change_pct DESC LIMIT ?
            )
            UNION ALL
            SELECT * FROM (
                SELECT *, 'loser' AS mover_type FROM with_change ORDER BY change_pct ASC LIMIT ?
            )
        """, (index_name, limit, limit)).fetchall()

        result = [dict(r) for r in rows]
        gainers = [r for r in result if r["mover_type"] == "gainer"]
        losers = [r for r in result if r["mover_type"] == "loser"]
        elapsed = time.time() - t0
        logger.info("GET /api/index/%s/movers — %d gainers, %d losers, %.3fs", name, len(gainers), len(losers), elapsed)
        return {"index_name": index_name, "gainers": gainers, "losers": losers}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/index/%s/movers — failed: %s", name, e)
        raise
    finally:
        conn.close()


@router.get("/{name}/technicals")
def index_technicals(name: str):
    """Technical indicators (DMA 50/200, RSI, 52W high/low) for each constituent."""
    logger.info("GET /api/index/%s/technicals", name)
    t0 = time.time()
    index_name = _resolve_index_name(name)
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            WITH constituents AS (
                SELECT i.instrument_id, i.symbol, i.name
                FROM classifications cl
                JOIN instruments i ON cl.instrument_id = i.instrument_id
                WHERE cl.classification_type = 'index_constituent'
                  AND cl.classification_name = ?
                  AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
            ),
            latest_tech AS (
                SELECT dt.instrument_id, dt.indicator_code, dt.value, dt.trade_date,
                       ROW_NUMBER() OVER (PARTITION BY dt.instrument_id, dt.indicator_code ORDER BY dt.trade_date DESC) AS rn
                FROM derived_technicals dt
                JOIN constituents c ON dt.instrument_id = c.instrument_id
                WHERE dt.indicator_code IN ('dma_50', 'dma_200', 'rsi_14', 'high_52w', 'low_52w', 'volume_avg_20d', 'daily_change_pct')
            ),
            pivoted AS (
                SELECT instrument_id,
                       MAX(CASE WHEN indicator_code = 'dma_50' THEN value END) AS dma_50,
                       MAX(CASE WHEN indicator_code = 'dma_200' THEN value END) AS dma_200,
                       MAX(CASE WHEN indicator_code = 'rsi_14' THEN value END) AS rsi_14,
                       MAX(CASE WHEN indicator_code = 'high_52w' THEN value END) AS high_52w,
                       MAX(CASE WHEN indicator_code = 'low_52w' THEN value END) AS low_52w,
                       MAX(CASE WHEN indicator_code = 'volume_avg_20d' THEN value END) AS volume_avg_20d,
                       MAX(CASE WHEN indicator_code = 'daily_change_pct' THEN value END) AS daily_change_pct,
                       MAX(trade_date) AS as_of
                FROM latest_tech WHERE rn = 1
                GROUP BY instrument_id
            )
            SELECT c.symbol, c.name, p.*
            FROM constituents c
            LEFT JOIN pivoted p ON c.instrument_id = p.instrument_id
            ORDER BY c.symbol
        """, (index_name,)).fetchall()

        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/index/%s/technicals — %d stocks, %.3fs", name, len(result), elapsed)
        return {"index_name": index_name, "technicals": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/index/%s/technicals — failed: %s", name, e)
        raise
    finally:
        conn.close()


@router.get("/{name}/breadth")
def index_breadth(name: str):
    """Advances/declines within an index based on latest daily change."""
    logger.info("GET /api/index/%s/breadth", name)
    t0 = time.time()
    index_name = _resolve_index_name(name)
    conn = get_pipeline_connection()
    try:
        row = conn.execute("""
            WITH constituents AS (
                SELECT i.instrument_id
                FROM classifications cl
                JOIN instruments i ON cl.instrument_id = i.instrument_id
                WHERE cl.classification_type = 'index_constituent'
                  AND cl.classification_name = ?
                  AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
            ),
            latest AS (
                SELECT dt.instrument_id, dt.value AS change_pct
                FROM derived_technicals dt
                JOIN constituents c ON dt.instrument_id = c.instrument_id
                WHERE dt.indicator_code = 'daily_change_pct'
                  AND dt.trade_date = (
                      SELECT MAX(dt2.trade_date) FROM derived_technicals dt2
                      WHERE dt2.instrument_id = dt.instrument_id AND dt2.indicator_code = 'daily_change_pct'
                  )
            )
            SELECT
                SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END) AS advances,
                SUM(CASE WHEN change_pct < 0 THEN 1 ELSE 0 END) AS declines,
                SUM(CASE WHEN change_pct = 0 THEN 1 ELSE 0 END) AS unchanged,
                COUNT(*) AS total
            FROM latest
        """, (index_name,)).fetchone()

        result = dict(row) if row else {"advances": 0, "declines": 0, "unchanged": 0, "total": 0}
        elapsed = time.time() - t0
        logger.info("GET /api/index/%s/breadth — %.3fs", name, elapsed)
        return {"index_name": index_name, "breadth": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/index/%s/breadth — failed: %s", name, e)
        raise
    finally:
        conn.close()
