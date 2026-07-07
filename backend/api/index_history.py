"""
Index history API: multi-instrument overlay series, range stats
(52W / 3Y / all-time high-low), and equal-weight classification baskets.

Powers the /indices dashboard page: compare standard indices (India +
global), stocks (pair comparison for portfolio building), and custom
indices built from classification groups (themes, niche indices, sectors).
"""
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/index-history", tags=["index-history"])

_MAX_SYMBOLS = 4

_RANGE_DAYS = {"1y": 365, "3y": 1095, "5y": 1825, "max": None}


def _series_for_instrument(conn, instrument_id: int, range_days: Optional[int]):
    date_filter = ""
    params: list = [instrument_id]
    if range_days is not None:
        date_filter = "AND trade_date >= date('now', ?)"
        params.append(f"-{range_days} days")
    rows = conn.execute(f"""
        SELECT trade_date, close FROM best_prices
        WHERE instrument_id = ? {date_filter}
        ORDER BY trade_date ASC
    """, params).fetchall()
    return [(r["trade_date"], r["close"]) for r in rows if r["close"] is not None]


def _resolve_symbols(conn, symbols: List[str]):
    """symbol → instrument row; 404 on the first unknown symbol."""
    out = []
    for sym in symbols:
        row = conn.execute(
            "SELECT instrument_id, symbol, name, instrument_type FROM instruments "
            "WHERE symbol = ? AND is_active = 1 "
            "ORDER BY CASE instrument_type WHEN 'index' THEN 0 WHEN 'stock' THEN 1 ELSE 2 END "
            "LIMIT 1",
            (sym.upper(),)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Instrument '{sym}' not found")
        out.append(row)
    return out


@router.get("/catalog")
def catalog():
    """Instruments with price data, grouped for the picker."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            SELECT i.symbol, i.name, i.instrument_type, i.exchange,
                   COUNT(ph.price_id) AS price_rows
            FROM instruments i
            JOIN price_history ph ON ph.instrument_id = i.instrument_id
            WHERE i.is_active = 1
            GROUP BY i.instrument_id
            HAVING price_rows >= 30
            ORDER BY i.instrument_type, i.symbol
        """).fetchall()
        groups: dict = {}
        for r in rows:
            groups.setdefault(r["instrument_type"], []).append({
                "symbol": r["symbol"], "name": r["name"], "exchange": r["exchange"],
            })
        # Classification groups usable as custom baskets
        baskets = conn.execute("""
            SELECT classification_type, classification_name,
                   COUNT(DISTINCT instrument_id) AS members
            FROM active_classifications
            WHERE classification_type IN ('sector', 'theme', 'niche_index', 'business_group')
            GROUP BY classification_type, classification_name
            HAVING members >= 3
            ORDER BY classification_type, classification_name
        """).fetchall()
        logger.info("GET /api/index-history/catalog — %.3fs", time.time() - t0)
        return {
            "instruments": groups,
            "baskets": [dict(b) for b in baskets],
        }
    finally:
        conn.close()


@router.get("/series")
def series(
    symbols: str = Query(..., description="Comma-separated, max 4"),
    range: str = Query("3y", pattern="^(1y|3y|5y|max)$"),
    normalize: bool = Query(True),
):
    """Daily close series for up to 4 instruments.

    normalize=true rebases each series to 100 at its first date within
    the range — the standard way to overlay instruments with different
    price levels (portfolio-building comparison).
    """
    syms = [s.strip() for s in symbols.split(",") if s.strip()][:_MAX_SYMBOLS]
    if not syms:
        raise HTTPException(status_code=400, detail="No symbols given")
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        instruments = _resolve_symbols(conn, syms)
        out = []
        for inst in instruments:
            pts = _series_for_instrument(conn, inst["instrument_id"], _RANGE_DAYS[range])
            if normalize and pts:
                base = pts[0][1]
                data = [{"time": d, "value": round(v / base * 100.0, 2)} for d, v in pts]
            else:
                data = [{"time": d, "value": v} for d, v in pts]
            out.append({
                "symbol": inst["symbol"], "name": inst["name"],
                "instrument_type": inst["instrument_type"],
                "points": data,
            })
        logger.info("GET /api/index-history/series %s — %.3fs", symbols, time.time() - t0)
        return {"range": range, "normalized": normalize, "series": out}
    finally:
        conn.close()


@router.get("/stats")
def stats(symbols: str = Query(..., description="Comma-separated, max 4")):
    """52W / 3Y / all-time high-low per instrument, with distance from
    the latest close. All-time is bounded by our earliest stored price
    (first_date in the payload says how far back that is)."""
    syms = [s.strip() for s in symbols.split(",") if s.strip()][:_MAX_SYMBOLS]
    if not syms:
        raise HTTPException(status_code=400, detail="No symbols given")
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        out = []
        for inst in _resolve_symbols(conn, syms):
            pts = _series_for_instrument(conn, inst["instrument_id"], None)
            if not pts:
                out.append({"symbol": inst["symbol"], "available": False})
                continue
            last_date, last = pts[-1]

            def hl(window_pts):
                values = [v for _, v in window_pts]
                hi, lo = max(values), min(values)
                return {
                    "high": hi, "low": lo,
                    "off_high_pct": round((last / hi - 1.0) * 100.0, 1),
                    "off_low_pct": round((last / lo - 1.0) * 100.0, 1),
                }

            def window(days):
                cutoff = conn.execute(
                    "SELECT date(?, ?)", (last_date, f"-{days} days")).fetchone()[0]
                return [p for p in pts if p[0] >= cutoff]

            out.append({
                "symbol": inst["symbol"], "name": inst["name"],
                "instrument_type": inst["instrument_type"],
                "available": True,
                "last": last, "last_date": last_date,
                "first_date": pts[0][0],
                "w52": hl(window(365)),
                "y3": hl(window(1095)),
                "alltime": hl(pts),
            })
        logger.info("GET /api/index-history/stats %s — %.3fs", symbols, time.time() - t0)
        return {"stats": out}
    finally:
        conn.close()


@router.get("/basket")
def basket(
    classification_type: str = Query(...),
    name: str = Query(...),
    range: str = Query("3y", pattern="^(1y|3y|5y|max)$"),
):
    """Equal-weight synthetic index for a classification group.

    Each constituent is rebased to 100 at its first date in the window;
    the basket value on a day is the mean of rebased values across
    constituents that have data that day (min 3). This is the standard
    equal-weight construction and matches how the sector-performance
    job treats groups.
    """
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        members = conn.execute("""
            SELECT DISTINCT instrument_id FROM active_classifications
            WHERE classification_type = ? AND classification_name = ?
        """, (classification_type, name)).fetchall()
        if len(members) < 3:
            raise HTTPException(status_code=404,
                                detail=f"No basket '{classification_type}:{name}' (need ≥3 members)")

        range_days = _RANGE_DAYS[range]
        rebased_by_day: dict = {}
        counted = 0
        for m in members:
            pts = _series_for_instrument(conn, m["instrument_id"], range_days)
            if len(pts) < 30:
                continue
            counted += 1
            base = pts[0][1]
            for d, v in pts:
                rebased_by_day.setdefault(d, []).append(v / base * 100.0)

        min_members = max(3, counted // 2)
        points = [
            {"time": d, "value": round(sum(vals) / len(vals), 2)}
            for d, vals in sorted(rebased_by_day.items())
            if len(vals) >= min_members
        ]
        logger.info("GET /api/index-history/basket %s:%s — %d members, %.3fs",
                    classification_type, name, counted, time.time() - t0)
        return {
            "classification_type": classification_type, "name": name,
            "range": range, "members_used": counted, "points": points,
        }
    finally:
        conn.close()
