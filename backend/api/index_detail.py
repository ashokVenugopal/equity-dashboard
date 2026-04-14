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
                  AND ph.trade_date IN (SELECT DISTINCT trade_date FROM market_breadth WHERE (advances + declines) > 0 ORDER BY trade_date DESC LIMIT 10)
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


@router.get("/{slug}/stats")
def index_stats(slug: str):
    """
    Index-level stats for performance cards and technical panels:
    - Performance at multiple timeframes with constituent breadth distribution
    - SMA / EMA values for the index
    - Support & Resistance levels
    """
    logger.info("GET /api/index-detail/%s/stats", slug)
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

        if not idx_inst:
            slug_symbol = slug.upper().replace("-", "")
            idx_inst = conn.execute("""
                SELECT instrument_id, symbol, name FROM instruments
                WHERE instrument_type = 'index' AND symbol LIKE ? AND is_active = 1
                LIMIT 1
            """, (f"%{slug_symbol}%",)).fetchone()

        if not idx_inst:
            logger.warning("GET /api/index-detail/%s/stats — index instrument not found", slug)

        # ── Index Performance at timeframes ──
        performance = []
        if idx_inst:
            perf_rows = conn.execute("""
                WITH best_per_date AS (
                    SELECT trade_date, close,
                           ROW_NUMBER() OVER (PARTITION BY trade_date
                               ORDER BY CASE source WHEN 'nse_index' THEN 1 WHEN 'yahoo_finance' THEN 2 ELSE 3 END
                           ) AS src_rn
                    FROM price_history WHERE instrument_id = ?
                ),
                clean AS (SELECT trade_date, close FROM best_per_date WHERE src_rn = 1),
                latest AS (
                    SELECT close, trade_date FROM clean ORDER BY trade_date DESC LIMIT 1
                )
                SELECT l.close AS current_close, l.trade_date,
                       (SELECT c.close FROM clean c WHERE c.trade_date <= date(l.trade_date, '-1 day') ORDER BY c.trade_date DESC LIMIT 1) AS close_1d,
                       (SELECT c.close FROM clean c WHERE c.trade_date <= date(l.trade_date, '-7 days') ORDER BY c.trade_date DESC LIMIT 1) AS close_1w,
                       (SELECT c.close FROM clean c WHERE c.trade_date <= date(l.trade_date, '-30 days') ORDER BY c.trade_date DESC LIMIT 1) AS close_1m,
                       (SELECT c.close FROM clean c WHERE c.trade_date <= date(l.trade_date, '-90 days') ORDER BY c.trade_date DESC LIMIT 1) AS close_3m,
                       (SELECT c.close FROM clean c WHERE c.trade_date <= date(l.trade_date, '-180 days') ORDER BY c.trade_date DESC LIMIT 1) AS close_6m,
                       (SELECT c.close FROM clean c WHERE c.trade_date <= date(l.trade_date, '-365 days') ORDER BY c.trade_date DESC LIMIT 1) AS close_1y
                FROM latest l
            """, (idx_inst["instrument_id"],)).fetchone()

            if perf_rows:
                cur = perf_rows["current_close"]
                for key, label, prev_key in [
                    ("1d", "1 Day", "close_1d"), ("1w", "1 Week", "close_1w"),
                    ("1m", "1 Month", "close_1m"), ("3m", "3 Month", "close_3m"),
                    ("6m", "6 Month", "close_6m"), ("1y", "1 Year", "close_1y"),
                ]:
                    prev = perf_rows[prev_key]
                    pct = round((cur - prev) / prev * 100, 2) if prev and prev > 0 else None
                    performance.append({"key": key, "label": label, "change_pct": pct})

        # ── Constituent breadth per timeframe ──
        constituents = conn.execute("""
            SELECT i.instrument_id
            FROM classifications cl
            JOIN instruments i ON cl.instrument_id = i.instrument_id
            WHERE cl.classification_type = 'index_constituent'
              AND cl.classification_name = ?
              AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
              AND i.is_active = 1
            GROUP BY i.instrument_id
        """, (index_name,)).fetchall()

        constituent_ids = [r["instrument_id"] for r in constituents]
        total = len(constituent_ids)

        if constituent_ids:
            placeholders = ",".join("?" * len(constituent_ids))
            breadth_rows = conn.execute(f"""
                WITH best_per_date AS (
                    SELECT ph.instrument_id, ph.trade_date, ph.close,
                           ROW_NUMBER() OVER (
                               PARTITION BY ph.instrument_id, ph.trade_date
                               ORDER BY CASE ph.source WHEN 'nse_bhavcopy' THEN 1 ELSE 2 END
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
                    SELECT l.instrument_id, l.close AS cur,
                           (SELECT c.close FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date <= date(l.trade_date, '-1 day') ORDER BY c.trade_date DESC LIMIT 1) AS p_1d,
                           (SELECT c.close FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date <= date(l.trade_date, '-7 days') ORDER BY c.trade_date DESC LIMIT 1) AS p_1w,
                           (SELECT c.close FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date <= date(l.trade_date, '-30 days') ORDER BY c.trade_date DESC LIMIT 1) AS p_1m,
                           (SELECT c.close FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date <= date(l.trade_date, '-90 days') ORDER BY c.trade_date DESC LIMIT 1) AS p_3m,
                           (SELECT c.close FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date <= date(l.trade_date, '-180 days') ORDER BY c.trade_date DESC LIMIT 1) AS p_6m,
                           (SELECT c.close FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date <= date(l.trade_date, '-365 days') ORDER BY c.trade_date DESC LIMIT 1) AS p_1y
                    FROM latest l WHERE l.rn = 1
                )
                SELECT
                    SUM(CASE WHEN p_1d > 0 AND cur > p_1d THEN 1 ELSE 0 END) AS adv_1d,
                    SUM(CASE WHEN p_1w > 0 AND cur > p_1w THEN 1 ELSE 0 END) AS adv_1w,
                    SUM(CASE WHEN p_1m > 0 AND cur > p_1m THEN 1 ELSE 0 END) AS adv_1m,
                    SUM(CASE WHEN p_3m > 0 AND cur > p_3m THEN 1 ELSE 0 END) AS adv_3m,
                    SUM(CASE WHEN p_6m > 0 AND cur > p_6m THEN 1 ELSE 0 END) AS adv_6m,
                    SUM(CASE WHEN p_1y > 0 AND cur > p_1y THEN 1 ELSE 0 END) AS adv_1y
                FROM lookbacks
            """, constituent_ids).fetchone()

            if breadth_rows:
                for p, bkey in zip(performance, ["adv_1d", "adv_1w", "adv_1m", "adv_3m", "adv_6m", "adv_1y"]):
                    adv = breadth_rows[bkey] or 0
                    p["advances"] = adv
                    p["declines"] = total - adv
                    p["total"] = total

        # ── Index Technicals (SMA / RSI) ──
        technicals = {}
        if idx_inst:
            tech_rows = conn.execute("""
                SELECT dt.indicator_code, dt.value
                FROM derived_technicals dt
                WHERE dt.instrument_id = ?
                  AND dt.indicator_code IN ('dma_50', 'dma_200', 'rsi_14')
                  AND dt.trade_date = (
                      SELECT MAX(dt2.trade_date) FROM derived_technicals dt2
                      WHERE dt2.instrument_id = dt.instrument_id AND dt2.indicator_code = dt.indicator_code
                  )
            """, (idx_inst["instrument_id"],)).fetchall()
            for r in tech_rows:
                technicals[r["indicator_code"]] = r["value"]

            # Also compute SMA 30 and SMA 100 from price history if not in derived_technicals
            for period in [30, 100]:
                key = f"dma_{period}"
                if key not in technicals:
                    sma_row = conn.execute("""
                        WITH best_per_date AS (
                            SELECT trade_date, close,
                                   ROW_NUMBER() OVER (PARTITION BY trade_date
                                       ORDER BY CASE source WHEN 'nse_index' THEN 1 ELSE 2 END
                                   ) AS src_rn
                            FROM price_history WHERE instrument_id = ?
                        )
                        SELECT AVG(close) AS sma
                        FROM (SELECT close FROM best_per_date WHERE src_rn = 1 ORDER BY trade_date DESC LIMIT ?)
                    """, (idx_inst["instrument_id"], period)).fetchone()
                    if sma_row and sma_row["sma"]:
                        technicals[key] = round(sma_row["sma"], 2)

        # ── Index S&R (from prev day H/L/C) ──
        support_resistance = {}
        if idx_inst:
            sr_row = conn.execute("""
                WITH best_per_date AS (
                    SELECT trade_date, high, low, close,
                           ROW_NUMBER() OVER (PARTITION BY trade_date
                               ORDER BY CASE source WHEN 'nse_index' THEN 1 ELSE 2 END
                           ) AS src_rn
                    FROM price_history WHERE instrument_id = ?
                ),
                ranked AS (
                    SELECT *, ROW_NUMBER() OVER (ORDER BY trade_date DESC) AS rn
                    FROM best_per_date WHERE src_rn = 1
                )
                SELECT high, low, close FROM ranked WHERE rn = 2
            """, (idx_inst["instrument_id"],)).fetchone()

            if sr_row and sr_row["high"] and sr_row["low"] and sr_row["close"]:
                h, l, c = sr_row["high"], sr_row["low"], sr_row["close"]
                pivot = round((h + l + c) / 3, 2)
                support_resistance = {
                    "pivot": pivot,
                    "r1": round(2 * pivot - l, 2),
                    "r2": round(pivot + (h - l), 2),
                    "r3": round(h + 2 * (pivot - l), 2),
                    "s1": round(2 * pivot - h, 2),
                    "s2": round(pivot - (h - l), 2),
                    "s3": round(l - 2 * (h - pivot), 2),
                }

        elapsed = time.time() - t0
        perf_count = sum(1 for p in performance if p.get("change_pct") is not None)
        tech_count = len(technicals)
        sr_count = len(support_resistance)
        if perf_count == 0:
            logger.warning("GET /api/index-detail/%s/stats — no performance data available", slug)
        if tech_count == 0:
            logger.warning("GET /api/index-detail/%s/stats — no technical indicators available", slug)
        logger.info(
            "GET /api/index-detail/%s/stats — %d perf timeframes, %d technicals, %d S&R levels, %d constituents — %.3fs",
            slug, perf_count, tech_count, sr_count, total, elapsed,
        )
        return {
            "index_name": index_name,
            "performance": performance,
            "technicals": technicals,
            "support_resistance": support_resistance,
        }
    except Exception as e:
        logger.error("GET /api/index-detail/%s/stats — failed: %s", slug, e)
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

        if view == "this_view":
            rows = _view_this_view(conn, instrument_ids, stocks)
        elif view == "overview":
            rows = _view_overview(conn, instrument_ids, stocks)
        elif view == "shareholding":
            rows = _view_shareholding(conn, company_ids, stocks)
        elif view == "relative":
            rows = _view_relative(conn, instrument_ids, stocks)
        elif view == "technicals":
            rows = _view_technicals(conn, instrument_ids, stocks)
        elif view == "support_resistance":
            rows = _view_support_resistance(conn, instrument_ids, stocks)
        elif view == "fundamentals":
            rows = _view_fundamentals(conn, company_ids, stocks)
        elif view == "price_volume":
            rows = _view_price_volume(conn, instrument_ids, stocks)
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
              AND ph.trade_date IN (SELECT DISTINCT trade_date FROM market_breadth WHERE (advances + declines) > 0 ORDER BY trade_date DESC LIMIT 10)
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


def _view_support_resistance(conn, instrument_ids, stocks):
    """
    Standard Pivot Point, R1-R3, S1-S3 calculated from previous day's H/L/C.
    Pivot = (H + L + C) / 3
    """
    placeholders = ",".join("?" * len(instrument_ids))
    rows = conn.execute(f"""
        WITH best_per_date AS (
            SELECT ph.instrument_id, ph.trade_date, ph.high, ph.low, ph.close,
                   ROW_NUMBER() OVER (
                       PARTITION BY ph.instrument_id, ph.trade_date
                       ORDER BY CASE ph.source WHEN 'nse_bhavcopy' THEN 1 WHEN 'bse_bhavcopy' THEN 2 ELSE 3 END
                   ) AS src_rn
            FROM price_history ph WHERE ph.instrument_id IN ({placeholders})
              AND ph.trade_date IN (SELECT DISTINCT trade_date FROM market_breadth WHERE (advances + declines) > 0 ORDER BY trade_date DESC LIMIT 10)
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY trade_date DESC) AS rn
            FROM best_per_date WHERE src_rn = 1
        )
        SELECT lp.instrument_id, lp.close AS current_close,
               pp.high AS prev_high, pp.low AS prev_low, pp.close AS prev_close
        FROM ranked lp
        LEFT JOIN ranked pp ON lp.instrument_id = pp.instrument_id AND pp.rn = 2
        WHERE lp.rn = 1
    """, instrument_ids).fetchall()

    result = []
    for r in rows:
        s = stocks.get(r["instrument_id"], {})
        close = r["current_close"]
        h, l, c = r["prev_high"], r["prev_low"], r["prev_close"]
        if h and l and c:
            pivot = round((h + l + c) / 3, 2)
            r1 = round(2 * pivot - l, 2)
            s1 = round(2 * pivot - h, 2)
            r2 = round(pivot + (h - l), 2)
            s2 = round(pivot - (h - l), 2)
            r3 = round(h + 2 * (pivot - l), 2)
            s3 = round(l - 2 * (h - pivot), 2)
        else:
            pivot = r1 = s1 = r2 = s2 = r3 = s3 = None

        result.append({
            "symbol": s.get("symbol"), "name": s.get("company_name"),
            "close": close, "pivot": pivot,
            "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3,
            "r1_diff_pct": round((r1 - close) / close * 100, 2) if r1 and close else None,
            "s1_diff_pct": round((s1 - close) / close * 100, 2) if s1 and close else None,
        })
    return sorted(result, key=lambda x: x.get("symbol", ""))


def _view_fundamentals(conn, company_ids, stocks):
    """PE, PEG, PBV, EPS, Market Cap, NPM, ROE."""
    if not company_ids:
        return []
    placeholders = ",".join("?" * len(company_ids))
    concepts = ["price_to_earning", "peg_ratio", "price_to_book", "eps", "market_cap", "npm", "roe"]
    concept_ph = ",".join("?" * len(concepts))
    rows = conn.execute(f"""
        SELECT f.company_id, c.concept_code, f.value
        FROM facts f
        JOIN sources s ON f.source_id = s.source_id
        JOIN concepts c ON f.concept_id = c.concept_id
        WHERE f.company_id IN ({placeholders})
          AND c.concept_code IN ({concept_ph})
          AND s.period_type IN ('annual', 'snapshot')
          AND f.fact_id = (
              SELECT f2.fact_id FROM facts f2
              JOIN sources s2 ON f2.source_id = s2.source_id
              JOIN concepts c2 ON f2.concept_id = c2.concept_id
              WHERE c2.concept_code = c.concept_code AND f2.company_id = f.company_id
                AND s2.period_type IN ('annual', 'snapshot')
              ORDER BY f2.period_end_date DESC, f2.created_at DESC LIMIT 1
          )
    """, company_ids + concepts).fetchall()

    by_company: dict = {}
    for r in rows:
        cid = r["company_id"]
        if cid not in by_company:
            by_company[cid] = {}
        by_company[cid][r["concept_code"]] = r["value"]

    cid_to_stock = {s["company_id"]: s for s in stocks.values() if s.get("company_id")}
    result = []
    for cid, vals in by_company.items():
        s = cid_to_stock.get(cid, {})
        result.append({
            "symbol": s.get("symbol"), "name": s.get("company_name"),
            "pe": vals.get("price_to_earning"), "peg": vals.get("peg_ratio"),
            "pb": vals.get("price_to_book"), "eps": vals.get("eps"),
            "market_cap": vals.get("market_cap"), "npm": vals.get("npm"), "roe": vals.get("roe"),
        })
    return sorted(result, key=lambda x: x.get("symbol", ""))


def _view_price_volume(conn, instrument_ids, stocks):
    """Day/Week/Month/Qtr/Year High-Low ranges."""
    placeholders = ",".join("?" * len(instrument_ids))
    rows = conn.execute(f"""
        WITH best_per_date AS (
            SELECT ph.instrument_id, ph.trade_date, ph.high, ph.low, ph.close, ph.volume,
                   ROW_NUMBER() OVER (
                       PARTITION BY ph.instrument_id, ph.trade_date
                       ORDER BY CASE ph.source WHEN 'nse_bhavcopy' THEN 1 ELSE 2 END
                   ) AS src_rn
            FROM price_history ph WHERE ph.instrument_id IN ({placeholders})
        ),
        clean AS (SELECT * FROM best_per_date WHERE src_rn = 1),
        latest AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY trade_date DESC) AS rn
            FROM clean
        ),
        ranges AS (
            SELECT l.instrument_id, l.close, l.volume, l.high AS day_high, l.low AS day_low,
                   (SELECT MAX(c.high) FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date >= date(l.trade_date, '-7 days')) AS week_high,
                   (SELECT MIN(c.low) FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date >= date(l.trade_date, '-7 days')) AS week_low,
                   (SELECT MAX(c.high) FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date >= date(l.trade_date, '-30 days')) AS month_high,
                   (SELECT MIN(c.low) FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date >= date(l.trade_date, '-30 days')) AS month_low,
                   (SELECT MAX(c.high) FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date >= date(l.trade_date, '-365 days')) AS year_high,
                   (SELECT MIN(c.low) FROM clean c WHERE c.instrument_id = l.instrument_id AND c.trade_date >= date(l.trade_date, '-365 days')) AS year_low
            FROM latest l WHERE l.rn = 1
        )
        SELECT * FROM ranges
    """, instrument_ids).fetchall()

    result = []
    for r in rows:
        s = stocks.get(r["instrument_id"], {})
        close = r["close"]
        def pct(low, high):
            return round((close - low) / (high - low) * 100, 1) if low and high and high != low and close else None
        result.append({
            "symbol": s.get("symbol"), "name": s.get("company_name"),
            "close": close, "volume": r["volume"],
            "day_high": r["day_high"], "day_low": r["day_low"], "day_pct": pct(r["day_low"], r["day_high"]),
            "week_high": r["week_high"], "week_low": r["week_low"], "week_pct": pct(r["week_low"], r["week_high"]),
            "month_high": r["month_high"], "month_low": r["month_low"], "month_pct": pct(r["month_low"], r["month_high"]),
            "year_high": r["year_high"], "year_low": r["year_low"], "year_pct": pct(r["year_low"], r["year_high"]),
        })
    return sorted(result, key=lambda x: x.get("symbol", ""))


def _view_this_view(conn, instrument_ids, stocks):
    """
    Trendlyne 'This View': LTP, change%, market cap, volume,
    3M sparkline data, and 52W high-low range with position indicator.
    """
    logger.info("Building this_view for %d instruments ...", len(instrument_ids))
    placeholders = ",".join("?" * len(instrument_ids))

    # Latest price + change + 52W range
    price_rows = conn.execute(f"""
        WITH best_per_date AS (
            SELECT ph.instrument_id, ph.trade_date, ph.close, ph.volume,
                   ROW_NUMBER() OVER (
                       PARTITION BY ph.instrument_id, ph.trade_date
                       ORDER BY CASE ph.source WHEN 'nse_bhavcopy' THEN 1 WHEN 'bse_bhavcopy' THEN 2 ELSE 3 END
                   ) AS src_rn
            FROM price_history ph WHERE ph.instrument_id IN ({placeholders})
              AND ph.trade_date IN (SELECT DISTINCT trade_date FROM market_breadth WHERE (advances + declines) > 0 ORDER BY trade_date DESC LIMIT 10)
        ),
        clean AS (SELECT * FROM best_per_date WHERE src_rn = 1),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY trade_date DESC) AS rn
            FROM clean
        ),
        ranges AS (
            SELECT r.instrument_id, r.close, r.volume, r.trade_date,
                   pv.close AS prev_close,
                   CASE WHEN pv.close > 0 THEN ROUND((r.close - pv.close) / pv.close * 100, 2) ELSE NULL END AS change_pct,
                   (SELECT MAX(c.close) FROM clean c WHERE c.instrument_id = r.instrument_id AND c.trade_date >= date(r.trade_date, '-365 days')) AS high_52w,
                   (SELECT MIN(c.close) FROM clean c WHERE c.instrument_id = r.instrument_id AND c.trade_date >= date(r.trade_date, '-365 days')) AS low_52w
            FROM ranked r
            LEFT JOIN ranked pv ON r.instrument_id = pv.instrument_id AND pv.rn = 2
            WHERE r.rn = 1
        )
        SELECT * FROM ranges
    """, instrument_ids).fetchall()

    price_map = {r["instrument_id"]: dict(r) for r in price_rows}

    # 3M sparkline: last 90 days of closes per instrument
    sparkline_rows = conn.execute(f"""
        WITH best_per_date AS (
            SELECT ph.instrument_id, ph.trade_date, ph.close,
                   ROW_NUMBER() OVER (
                       PARTITION BY ph.instrument_id, ph.trade_date
                       ORDER BY CASE ph.source WHEN 'nse_bhavcopy' THEN 1 ELSE 2 END
                   ) AS src_rn
            FROM price_history ph WHERE ph.instrument_id IN ({placeholders})
        ),
        clean AS (SELECT * FROM best_per_date WHERE src_rn = 1),
        numbered AS (
            SELECT instrument_id, trade_date, close,
                   ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY trade_date DESC) AS rn
            FROM clean
        )
        SELECT instrument_id, trade_date, close
        FROM numbered WHERE rn <= 90
        ORDER BY instrument_id, trade_date ASC
    """, instrument_ids).fetchall()

    sparklines: dict = {}
    for r in sparkline_rows:
        iid = r["instrument_id"]
        if iid not in sparklines:
            sparklines[iid] = []
        sparklines[iid].append({"t": r["trade_date"], "c": r["close"]})

    # Market cap from facts
    company_ids = [s["company_id"] for s in stocks.values() if s.get("company_id")]
    mcap_map = {}
    if company_ids:
        cp = ",".join("?" * len(company_ids))
        mcap_rows = conn.execute(f"""
            SELECT f.company_id, f.value
            FROM facts f
            JOIN sources s ON f.source_id = s.source_id
            JOIN concepts c ON f.concept_id = c.concept_id
            WHERE f.company_id IN ({cp})
              AND c.concept_code = 'market_cap'
              AND s.period_type IN ('annual', 'snapshot')
              AND f.fact_id = (
                  SELECT f2.fact_id FROM facts f2
                  JOIN sources s2 ON f2.source_id = s2.source_id
                  JOIN concepts c2 ON f2.concept_id = c2.concept_id
                  WHERE c2.concept_code = 'market_cap' AND f2.company_id = f.company_id
                    AND s2.period_type IN ('annual', 'snapshot')
                  ORDER BY f2.period_end_date DESC, f2.created_at DESC LIMIT 1
              )
        """, company_ids).fetchall()
        for r in mcap_rows:
            mcap_map[r["company_id"]] = r["value"]

    result = []
    for iid, s in stocks.items():
        p = price_map.get(iid, {})
        close = p.get("close")
        high_52w = p.get("high_52w")
        low_52w = p.get("low_52w")

        range_pct = None
        if close and high_52w and low_52w and high_52w != low_52w:
            range_pct = round((close - low_52w) / (high_52w - low_52w) * 100, 1)

        result.append({
            "symbol": s.get("symbol"),
            "name": s.get("company_name"),
            "close": close,
            "change_pct": p.get("change_pct"),
            "volume": p.get("volume"),
            "market_cap": mcap_map.get(s.get("company_id")),
            "high_52w": high_52w,
            "low_52w": low_52w,
            "range_pct": range_pct,
            "sparkline": sparklines.get(iid, []),
        })
    with_sparkline = sum(1 for r in result if r.get("sparkline"))
    with_range = sum(1 for r in result if r.get("range_pct") is not None)
    with_mcap = sum(1 for r in result if r.get("market_cap") is not None)
    logger.info(
        "this_view built — %d rows, %d with sparkline, %d with 52W range, %d with mcap",
        len(result), with_sparkline, with_range, with_mcap,
    )
    return sorted(result, key=lambda x: x.get("symbol") or "")
