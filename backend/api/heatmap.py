"""
Heatmap API endpoint.

Generates treemap data: size proportional to market_cap, color mapped to daily % change.
"""
import logging
import time

from fastapi import APIRouter, HTTPException, Query

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/heatmap", tags=["heatmap"])


@router.get("/{index}")
def heatmap_data(index: str):
    """
    Treemap heatmap for an index.
    Returns each constituent with market_cap (size) and daily_change_pct (color).
    """
    logger.info("GET /api/heatmap/%s", index)
    t0 = time.time()
    # Resolve slug
    from backend.api.index import _resolve_index_name
    index_name = _resolve_index_name(index)

    conn = get_pipeline_connection()
    try:
        # Dedup classifications + direct price_history query (no slow best_prices view)
        rows = conn.execute("""
            WITH constituents AS (
                SELECT i.instrument_id, i.symbol, i.name, i.company_id
                FROM classifications cl
                JOIN instruments i ON cl.instrument_id = i.instrument_id
                WHERE cl.classification_type = 'index_constituent'
                  AND cl.classification_name = ?
                  AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
                  AND i.is_active = 1
                GROUP BY i.instrument_id
            ),
            best_per_date AS (
                SELECT ph.instrument_id, ph.trade_date, ph.close,
                       ROW_NUMBER() OVER (
                           PARTITION BY ph.instrument_id, ph.trade_date
                           ORDER BY CASE ph.source
                               WHEN 'nse_bhavcopy' THEN 1 WHEN 'bse_bhavcopy' THEN 2
                               WHEN 'yahoo_finance' THEN 3 ELSE 4
                           END
                       ) AS src_rn
                FROM price_history ph
                WHERE ph.instrument_id IN (SELECT instrument_id FROM constituents)
            ),
            ranked AS (
                SELECT instrument_id, trade_date, close,
                       ROW_NUMBER() OVER (
                           PARTITION BY instrument_id ORDER BY trade_date DESC
                       ) AS rn
                FROM best_per_date WHERE src_rn = 1
            ),
            market_caps AS (
                SELECT f.company_id, f.value AS market_cap
                FROM facts f
                JOIN sources s ON f.source_id = s.source_id
                JOIN concepts co ON f.concept_id = co.concept_id
                WHERE co.concept_code = 'market_cap'
                  AND f.company_id IN (SELECT company_id FROM constituents)
                  AND f.fact_id = (
                      SELECT f2.fact_id FROM facts f2
                      JOIN sources s2 ON f2.source_id = s2.source_id
                      JOIN concepts co2 ON f2.concept_id = co2.concept_id
                      WHERE co2.concept_code = 'market_cap'
                        AND f2.company_id = f.company_id
                      ORDER BY f2.period_end_date DESC,
                          CASE s2.derivation WHEN 'original' THEN 1 WHEN 'aggregated' THEN 2 ELSE 3 END,
                          CASE s2.file_type WHEN 'screener_excel' THEN 1 WHEN 'screener_web' THEN 2 ELSE 3 END,
                          f2.created_at DESC
                      LIMIT 1
                  )
            )
            SELECT c.symbol, c.name, c.company_id,
                   lp.close, lp.trade_date,
                   COALESCE(mc.market_cap, lp.close) AS market_cap,
                   CASE WHEN pv.close > 0
                        THEN ROUND((lp.close - pv.close) / pv.close * 100, 2)
                        ELSE NULL END AS change_pct
            FROM constituents c
            LEFT JOIN ranked lp ON c.instrument_id = lp.instrument_id AND lp.rn = 1
            LEFT JOIN ranked pv ON c.instrument_id = pv.instrument_id AND pv.rn = 2
            LEFT JOIN market_caps mc ON c.company_id = mc.company_id
            ORDER BY COALESCE(mc.market_cap, 0) DESC
        """, (index_name,)).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail=f"Index '{index_name}' not found or has no constituents")

        blocks = []
        for r in rows:
            blocks.append({
                "symbol": r["symbol"],
                "name": r["name"],
                "market_cap": r["market_cap"],
                "close": r["close"],
                "change_pct": r["change_pct"],
            })

        elapsed = time.time() - t0
        logger.info("GET /api/heatmap/%s — %d blocks, %.3fs", index, len(blocks), elapsed)
        return {"index_name": index_name, "blocks": blocks}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/heatmap/%s — failed: %s", index, e)
        raise
    finally:
        conn.close()
