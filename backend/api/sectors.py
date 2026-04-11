"""
Sectors & Themes API endpoints.

Multi-timeframe performance and drill-down to constituents.
Data sourced from sector_performance and classifications tables.
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sectors", tags=["sectors"])


@router.get("/performance")
def sector_performance(
    classification_type: str = Query("sector", description="sector, theme, business_group, index_constituent"),
    timeframe: Optional[str] = Query(None, description="1d, 1w, 2w, 4w, 13w, 26w, 52w, ytd"),
    metric: str = Query("avg_return_pct"),
):
    """
    Multi-timeframe performance for all groups of a given classification type.
    If no timeframe specified, returns latest data for all timeframes pivoted.
    """
    logger.info("GET /api/sectors/performance — classification_type=%s, timeframe=%s, metric=%s", classification_type, timeframe, metric)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        if timeframe:
            rows = conn.execute("""
                SELECT sp.classification_name, sp.timeframe, sp.metric, sp.value, sp.compute_date
                FROM sector_performance sp
                WHERE sp.classification_type = ?
                  AND sp.timeframe = ?
                  AND sp.metric = ?
                  AND sp.compute_date = (
                      SELECT MAX(sp2.compute_date) FROM sector_performance sp2
                      WHERE sp2.classification_type = sp.classification_type
                        AND sp2.classification_name = sp.classification_name
                        AND sp2.timeframe = sp.timeframe
                        AND sp2.metric = sp.metric
                  )
                ORDER BY sp.value DESC
            """, (classification_type, timeframe, metric)).fetchall()
            result = [dict(r) for r in rows]
        else:
            # Pivot: one row per classification_name with columns for each timeframe
            rows = conn.execute("""
                SELECT sp.classification_name, sp.timeframe, sp.value, sp.compute_date
                FROM sector_performance sp
                WHERE sp.classification_type = ?
                  AND sp.metric = ?
                  AND sp.compute_date = (
                      SELECT MAX(sp2.compute_date) FROM sector_performance sp2
                      WHERE sp2.classification_type = sp.classification_type
                        AND sp2.classification_name = sp.classification_name
                        AND sp2.timeframe = sp.timeframe
                        AND sp2.metric = sp.metric
                  )
                ORDER BY sp.classification_name, sp.timeframe
            """, (classification_type, metric)).fetchall()

            pivoted = {}
            for r in rows:
                name = r["classification_name"]
                if name not in pivoted:
                    pivoted[name] = {"classification_name": name, "compute_date": r["compute_date"]}
                pivoted[name][r["timeframe"]] = r["value"]

            result = sorted(pivoted.values(), key=lambda x: x.get("1w", 0) or 0, reverse=True)

        elapsed = time.time() - t0
        logger.info("GET /api/sectors/performance — %d rows, %.3fs", len(result), elapsed)
        return {"classification_type": classification_type, "metric": metric, "performance": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/sectors/performance — failed: %s", e)
        raise
    finally:
        conn.close()


@router.get("/{classification_type}/{name}/constituents")
def sector_constituents(classification_type: str, name: str):
    """Stocks belonging to a sector/theme/group with latest price data."""
    logger.info("GET /api/sectors/%s/%s/constituents", classification_type, name)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        # Dedup classifications + direct price_history query
        rows = conn.execute("""
            WITH deduped AS (
                SELECT i.instrument_id, c.symbol, c.name, MIN(cl.sort_order) AS sort_order
                FROM classifications cl
                JOIN instruments i ON cl.instrument_id = i.instrument_id
                JOIN companies c ON i.company_id = c.company_id
                WHERE cl.classification_type = ?
                  AND cl.classification_name = ?
                  AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
                GROUP BY i.instrument_id
            ),
            lp AS (
                SELECT ph.instrument_id, ph.close, ph.trade_date, ph.volume,
                       ROW_NUMBER() OVER (
                           PARTITION BY ph.instrument_id
                           ORDER BY ph.trade_date DESC,
                               CASE ph.source
                                   WHEN 'nse_bhavcopy' THEN 1 WHEN 'bse_bhavcopy' THEN 2
                                   WHEN 'yahoo_finance' THEN 3 ELSE 4
                               END
                       ) AS rn
                FROM price_history ph
                WHERE ph.instrument_id IN (SELECT instrument_id FROM deduped)
            )
            SELECT d.symbol, d.name, lp.close, lp.trade_date, lp.volume
            FROM deduped d
            LEFT JOIN lp ON lp.instrument_id = d.instrument_id AND lp.rn = 1
            ORDER BY d.sort_order, d.symbol
        """, (classification_type, name)).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail=f"No constituents for {classification_type}/{name}")

        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/sectors/%s/%s/constituents — %d stocks, %.3fs",
                     classification_type, name, len(result), elapsed)
        return {"classification_type": classification_type, "name": name, "constituents": result, "count": len(result)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/sectors/%s/%s/constituents — failed: %s", classification_type, name, e)
        raise
    finally:
        conn.close()
