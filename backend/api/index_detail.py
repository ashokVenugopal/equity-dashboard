"""
Index Detail API endpoints.

Trendlyne-style index deep dive: index stats, constituent table with
switchable views (overview, shareholding, relative performance, technicals).
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.core.connection import get_pipeline_connection
from backend.api.index import _resolve_index_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/index-detail", tags=["index-detail"])


@router.get("/{slug}/overview")
def index_overview(slug: str):
    """
    Index-level overview: latest price, change, key stats.
    """
    logger.info("GET /api/index-detail/%s/overview", slug)
    t0 = time.time()
    index_name = _resolve_index_name(slug)
    conn = get_pipeline_connection()
    try:
        # Find the index instrument
        idx_inst = conn.execute("""
            SELECT instrument_id, symbol, name
            FROM instruments
            WHERE instrument_type = 'index' AND is_active = 1
              AND (symbol = ? OR name = ?)
            LIMIT 1
        """, (index_name, index_name)).fetchone()

        # Try slug-based symbol lookup
        if not idx_inst:
            slug_symbol = slug.upper().replace("-", "")
            idx_inst = conn.execute("""
                SELECT instrument_id, symbol, name FROM instruments
                WHERE instrument_type = 'index' AND symbol LIKE ? AND is_active = 1
                LIMIT 1
            """, (f"%{slug_symbol}%",)).fetchone()

        price_data = None
        if idx_inst:
            prices = conn.execute("""
                SELECT ph.trade_date, ph.open, ph.high, ph.low, ph.close, ph.volume,
                       ROW_NUMBER() OVER (ORDER BY ph.trade_date DESC,
                           CASE ph.source WHEN 'nse_index' THEN 1 WHEN 'yahoo_finance' THEN 2 ELSE 3 END
                       ) AS rn
                FROM price_history ph
                WHERE ph.instrument_id = ?
                ORDER BY ph.trade_date DESC LIMIT 2
            """, (idx_inst["instrument_id"],)).fetchall()

            if prices:
                latest = dict(prices[0])
                prev = dict(prices[1]) if len(prices) > 1 else None
                change = round(latest["close"] - prev["close"], 2) if prev and prev["close"] else None
                change_pct = round(change / prev["close"] * 100, 2) if change and prev["close"] else None
                price_data = {
                    "close": latest["close"],
                    "open": latest["open"],
                    "high": latest["high"],
                    "low": latest["low"],
                    "trade_date": latest["trade_date"],
                    "change": change,
                    "change_pct": change_pct,
                }

        # Count constituents
        count = conn.execute("""
            SELECT COUNT(DISTINCT instrument_id) AS cnt
            FROM classifications
            WHERE classification_type = 'index_constituent'
              AND classification_name = ?
              AND (effective_to IS NULL OR effective_to >= date('now'))
        """, (index_name,)).fetchone()

        elapsed = time.time() - t0
        logger.info("GET /api/index-detail/%s/overview — %.3fs", slug, elapsed)
        return {
            "index_name": index_name,
            "slug": slug,
            "instrument": dict(idx_inst) if idx_inst else None,
            "price": price_data,
            "constituent_count": count["cnt"] if count else 0,
        }
    except Exception as e:
        logger.error("GET /api/index-detail/%s/overview — failed: %s", slug, e)
        raise
    finally:
        conn.close()


@router.get("/{slug}/table")
def index_table(
    slug: str,
    view: str = Query("overview", description="overview, shareholding, relative, technicals"),
):
    """
    Constituent table with switchable views.
    - overview: Price, Change, Market Cap, Volume
    - shareholding: Promoter%, FII%, DII%, Public%
    - relative: 1d, 1w, 1m returns (from sector_performance or daily_change_pct)
    - technicals: DMA 50/200, RSI, 52W High/Low, Volume Ratio
    """
    logger.info("GET /api/index-detail/%s/table — view=%s", slug, view)
    t0 = time.time()
    index_name = _resolve_index_name(slug)
    conn = get_pipeline_connection()
    try:
        # Base: deduped constituent list
        base = conn.execute("""
            SELECT i.instrument_id, i.symbol, i.name AS company_name, i.company_id
            FROM classifications cl
            JOIN instruments i ON cl.instrument_id = i.instrument_id
            WHERE cl.classification_type = 'index_constituent'
              AND cl.classification_name = ?
              AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
              AND i.is_active = 1
            GROUP BY i.instrument_id
            ORDER BY i.symbol
        """, (index_name,)).fetchall()

        if not base:
            raise HTTPException(status_code=404, detail=f"Index '{index_name}' not found")

        instrument_ids = [r["instrument_id"] for r in base]
        company_ids = [r["company_id"] for r in base if r["company_id"]]
        stocks = {r["instrument_id"]: dict(r) for r in base}

        if view == "overview":
            rows = _view_overview(conn, instrument_ids, stocks)
        elif view == "shareholding":
            rows = _view_shareholding(conn, company_ids, stocks)
        elif view == "relative":
            rows = _view_relative(conn, instrument_ids, stocks)
        elif view == "technicals":
            rows = _view_technicals(conn, instrument_ids, stocks)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown view: {view}")

        elapsed = time.time() - t0
        logger.info("GET /api/index-detail/%s/table — view=%s, %d rows, %.3fs", slug, view, len(rows), elapsed)
        return {"index_name": index_name, "view": view, "rows": rows, "count": len(rows)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/index-detail/%s/table — failed: %s", slug, e)
        raise
    finally:
        conn.close()


def _view_overview(conn, instrument_ids, stocks):
    """Price, Change%, Market Cap, Volume."""
    placeholders = ",".join("?" * len(instrument_ids))
    rows = conn.execute(f"""
        WITH best_per_date AS (
            SELECT ph.instrument_id, ph.trade_date, ph.close, ph.volume,
                   ROW_NUMBER() OVER (
                       PARTITION BY ph.instrument_id, ph.trade_date
                       ORDER BY CASE ph.source
                           WHEN 'nse_bhavcopy' THEN 1 WHEN 'bse_bhavcopy' THEN 2 ELSE 3
                       END
                   ) AS src_rn
            FROM price_history ph WHERE ph.instrument_id IN ({placeholders})
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY trade_date DESC) AS rn
            FROM best_per_date WHERE src_rn = 1
        )
        SELECT lp.instrument_id, lp.close, lp.volume, lp.trade_date,
               pv.close AS prev_close,
               CASE WHEN pv.close > 0 THEN ROUND((lp.close - pv.close) / pv.close * 100, 2) ELSE NULL END AS change_pct
        FROM ranked lp
        LEFT JOIN ranked pv ON lp.instrument_id = pv.instrument_id AND pv.rn = 2
        WHERE lp.rn = 1
    """, instrument_ids).fetchall()

    result = []
    for r in rows:
        s = stocks.get(r["instrument_id"], {})
        result.append({
            "symbol": s.get("symbol"), "name": s.get("company_name"),
            "close": r["close"], "change_pct": r["change_pct"],
            "volume": r["volume"], "trade_date": r["trade_date"],
        })
    return sorted(result, key=lambda x: x.get("symbol") or "")


def _view_shareholding(conn, company_ids, stocks):
    """Promoter%, FII%, DII%, Public% for each stock."""
    if not company_ids:
        return []
    placeholders = ",".join("?" * len(company_ids))
    rows = conn.execute(f"""
        SELECT f.company_id, c.concept_code, f.value
        FROM facts f
        JOIN sources s ON f.source_id = s.source_id
        JOIN concepts c ON f.concept_id = c.concept_id
        WHERE f.company_id IN ({placeholders})
          AND c.concept_code IN ('sh_promoters', 'sh_fiis', 'sh_diis', 'sh_public')
          AND s.period_type IN ('annual', 'snapshot')
          AND f.fact_id = (
              SELECT f2.fact_id FROM facts f2
              JOIN sources s2 ON f2.source_id = s2.source_id
              JOIN concepts c2 ON f2.concept_id = c2.concept_id
              WHERE c2.concept_code = c.concept_code AND f2.company_id = f.company_id
                AND s2.period_type IN ('annual', 'snapshot')
              ORDER BY f2.period_end_date DESC, f2.created_at DESC LIMIT 1
          )
    """, company_ids).fetchall()

    by_company: dict = {}
    for r in rows:
        cid = r["company_id"]
        if cid not in by_company:
            by_company[cid] = {}
        by_company[cid][r["concept_code"]] = r["value"]

    # Map company_id back to symbol via stocks
    cid_to_stock = {}
    for s in stocks.values():
        if s.get("company_id"):
            cid_to_stock[s["company_id"]] = s

    result = []
    for cid, holdings in by_company.items():
        s = cid_to_stock.get(cid, {})
        result.append({
            "symbol": s.get("symbol"), "name": s.get("company_name"),
            "promoters": holdings.get("sh_promoters"),
            "fii": holdings.get("sh_fiis"),
            "dii": holdings.get("sh_diis"),
            "public": holdings.get("sh_public"),
        })
    return sorted(result, key=lambda x: x.get("symbol") or "")


def _view_relative(conn, instrument_ids, stocks):
    """1d, 1w, 1m, 3m, 6m, 1y relative performance."""
    placeholders = ",".join("?" * len(instrument_ids))
    # Get prices at different lookback dates
    rows = conn.execute(f"""
        WITH best_per_date AS (
            SELECT ph.instrument_id, ph.trade_date, ph.close,
                   ROW_NUMBER() OVER (
                       PARTITION BY ph.instrument_id, ph.trade_date
                       ORDER BY CASE ph.source WHEN 'nse_bhavcopy' THEN 1 WHEN 'bse_bhavcopy' THEN 2 ELSE 3 END
                   ) AS src_rn
            FROM price_history ph WHERE ph.instrument_id IN ({placeholders})
        ),
        clean AS (SELECT * FROM best_per_date WHERE src_rn = 1),
        latest AS (
            SELECT instrument_id, close, trade_date,
                   ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY trade_date DESC) AS rn
            FROM clean
        ),
        lookbacks AS (
            SELECT l.instrument_id, l.close AS current_close, l.trade_date,
                   (SELECT c.close FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date <= date(l.trade_date, '-7 days') ORDER BY c.trade_date DESC LIMIT 1) AS close_1w,
                   (SELECT c.close FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date <= date(l.trade_date, '-30 days') ORDER BY c.trade_date DESC LIMIT 1) AS close_1m,
                   (SELECT c.close FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date <= date(l.trade_date, '-90 days') ORDER BY c.trade_date DESC LIMIT 1) AS close_3m,
                   (SELECT c.close FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date <= date(l.trade_date, '-180 days') ORDER BY c.trade_date DESC LIMIT 1) AS close_6m,
                   (SELECT c.close FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date <= date(l.trade_date, '-365 days') ORDER BY c.trade_date DESC LIMIT 1) AS close_1y
            FROM latest l WHERE l.rn = 1
        )
        SELECT instrument_id, current_close, trade_date,
               CASE WHEN close_1w > 0 THEN ROUND((current_close - close_1w) / close_1w * 100, 2) END AS return_1w,
               CASE WHEN close_1m > 0 THEN ROUND((current_close - close_1m) / close_1m * 100, 2) END AS return_1m,
               CASE WHEN close_3m > 0 THEN ROUND((current_close - close_3m) / close_3m * 100, 2) END AS return_3m,
               CASE WHEN close_6m > 0 THEN ROUND((current_close - close_6m) / close_6m * 100, 2) END AS return_6m,
               CASE WHEN close_1y > 0 THEN ROUND((current_close - close_1y) / close_1y * 100, 2) END AS return_1y
        FROM lookbacks
    """, instrument_ids).fetchall()

    result = []
    for r in rows:
        s = stocks.get(r["instrument_id"], {})
        result.append({
            "symbol": s.get("symbol"), "name": s.get("company_name"),
            "close": r["current_close"],
            "return_1w": r["return_1w"], "return_1m": r["return_1m"],
            "return_3m": r["return_3m"], "return_6m": r["return_6m"],
            "return_1y": r["return_1y"],
        })
    return sorted(result, key=lambda x: x.get("symbol") or "")


def _view_technicals(conn, instrument_ids, stocks):
    """DMA 50/200, RSI 14, 52W High/Low, Volume Ratio."""
    placeholders = ",".join("?" * len(instrument_ids))
    rows = conn.execute(f"""
        WITH latest_tech AS (
            SELECT dt.instrument_id, dt.indicator_code, dt.value,
                   ROW_NUMBER() OVER (PARTITION BY dt.instrument_id, dt.indicator_code ORDER BY dt.trade_date DESC) AS rn
            FROM derived_technicals dt
            WHERE dt.instrument_id IN ({placeholders})
              AND dt.indicator_code IN ('dma_50', 'dma_200', 'rsi_14', 'high_52w', 'low_52w', 'volume_ratio')
        )
        SELECT instrument_id,
               MAX(CASE WHEN indicator_code = 'dma_50' THEN value END) AS dma_50,
               MAX(CASE WHEN indicator_code = 'dma_200' THEN value END) AS dma_200,
               MAX(CASE WHEN indicator_code = 'rsi_14' THEN value END) AS rsi_14,
               MAX(CASE WHEN indicator_code = 'high_52w' THEN value END) AS high_52w,
               MAX(CASE WHEN indicator_code = 'low_52w' THEN value END) AS low_52w,
               MAX(CASE WHEN indicator_code = 'volume_ratio' THEN value END) AS volume_ratio
        FROM latest_tech WHERE rn = 1
        GROUP BY instrument_id
    """, instrument_ids).fetchall()

    result = []
    for r in rows:
        s = stocks.get(r["instrument_id"], {})
        close = None
        # Get current close for distance calculations
        cp = conn.execute("""
            SELECT close FROM price_history
            WHERE instrument_id = ? ORDER BY trade_date DESC LIMIT 1
        """, (r["instrument_id"],)).fetchone()
        if cp:
            close = cp["close"]

        dist_high = round((close - r["high_52w"]) / r["high_52w"] * 100, 2) if close and r["high_52w"] else None
        dist_low = round((close - r["low_52w"]) / r["low_52w"] * 100, 2) if close and r["low_52w"] else None

        result.append({
            "symbol": s.get("symbol"), "name": s.get("company_name"),
            "close": close,
            "dma_50": r["dma_50"], "dma_200": r["dma_200"],
            "rsi_14": r["rsi_14"],
            "high_52w": r["high_52w"], "low_52w": r["low_52w"],
            "dist_from_high": dist_high, "dist_from_low": dist_low,
            "volume_ratio": r["volume_ratio"],
        })
    return sorted(result, key=lambda x: x.get("symbol") or "")
