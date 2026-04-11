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
    t0 = time.time()
    # Resolve slug
    from backend.api.index import _resolve_index_name
    index_name = _resolve_index_name(index)

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
            latest_price AS (
                SELECT bp.instrument_id, bp.close, bp.trade_date,
                       ROW_NUMBER() OVER (PARTITION BY bp.instrument_id ORDER BY bp.trade_date DESC) AS rn
                FROM best_prices bp
                JOIN constituents c ON bp.instrument_id = c.instrument_id
            ),
            prev_price AS (
                SELECT bp.instrument_id, bp.close AS prev_close,
                       ROW_NUMBER() OVER (PARTITION BY bp.instrument_id ORDER BY bp.trade_date DESC) AS rn
                FROM best_prices bp
                JOIN constituents c ON bp.instrument_id = c.instrument_id
                JOIN latest_price lp ON lp.instrument_id = bp.instrument_id AND lp.rn = 1
                WHERE bp.trade_date < lp.trade_date
            ),
            market_caps AS (
                SELECT bf.company_id,
                       bf.value AS market_cap
                FROM best_facts_consolidated bf
                JOIN concepts co ON bf.concept_id = co.concept_id
                WHERE co.concept_code = 'market_cap'
                  AND bf.fact_id = (
                      SELECT bf2.fact_id FROM best_facts_consolidated bf2
                      JOIN concepts co2 ON bf2.concept_id = co2.concept_id
                      WHERE co2.concept_code = 'market_cap'
                        AND bf2.company_id = bf.company_id
                      ORDER BY bf2.period_end_date DESC
                      LIMIT 1
                  )
            )
            SELECT c.symbol, c.name, c.company_id,
                   lp.close, lp.trade_date,
                   COALESCE(mc.market_cap, lp.close) AS market_cap,
                   CASE WHEN pp.prev_close > 0
                        THEN ROUND((lp.close - pp.prev_close) / pp.prev_close * 100, 2)
                        ELSE NULL END AS change_pct
            FROM constituents c
            LEFT JOIN latest_price lp ON c.instrument_id = lp.instrument_id AND lp.rn = 1
            LEFT JOIN prev_price pp ON c.instrument_id = pp.instrument_id AND pp.rn = 1
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
    finally:
        conn.close()
