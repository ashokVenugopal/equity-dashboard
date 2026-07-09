"""
Macro API: liquidity series (FRED + seeded India data) and the risk
calendar (market_events: FOMC/RBI/jobs seeds + NSE results, corporate
actions, IPOs).
"""
import logging
import time

from fastapi import APIRouter, HTTPException, Query

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/macro", tags=["macro"])

_MAX_CODES = 6


@router.get("/series")
def macro_series(
    codes: str = Query(..., description="Comma-separated series codes, max 6"),
    transform: str = Query("none", pattern="^(none|yoy)$"),
    start: str = Query("2015-01-01"),
):
    """Observations per series code.

    transform=yoy converts each point to % change vs the observation
    ~1 year earlier (nearest at least 360 days back) — for CPI-style
    index levels.
    """
    code_list = [c.strip().upper() for c in codes.split(",") if c.strip()][:_MAX_CODES]
    if not code_list:
        raise HTTPException(status_code=400, detail="No series codes given")
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        out = []
        for code in code_list:
            rows = conn.execute("""
                SELECT obs_date, value FROM macro_series
                WHERE series_code = ? AND obs_date >= ?
                ORDER BY obs_date ASC
            """, (code, start)).fetchall()
            pts = [(r["obs_date"], r["value"]) for r in rows]

            if transform == "yoy" and pts:
                # Need pre-window history for the first year's baselines.
                base_rows = conn.execute("""
                    SELECT obs_date, value FROM macro_series
                    WHERE series_code = ? AND obs_date >= date(?, '-400 days')
                    ORDER BY obs_date ASC
                """, (code, start)).fetchall()
                all_pts = [(r["obs_date"], r["value"]) for r in base_rows]
                dates = [d for d, _ in all_pts]
                from bisect import bisect_right
                from datetime import date, timedelta
                yoy = []
                for d, v in pts:
                    target = (date.fromisoformat(d) - timedelta(days=360)).isoformat()
                    idx = bisect_right(dates, target) - 1
                    if idx < 0:
                        continue
                    base = all_pts[idx][1]
                    if base:
                        yoy.append((d, round((v / base - 1.0) * 100.0, 2)))
                pts = yoy

            out.append({
                "code": code,
                "points": [{"time": d, "value": v} for d, v in pts],
            })
        logger.info("GET /api/macro/series %s — %.3fs", codes, time.time() - t0)
        return {"transform": transform, "series": out}
    finally:
        conn.close()


@router.get("/events")
def macro_events(
    days_ahead: int = Query(45, ge=1, le=365),
    days_back: int = Query(7, ge=0, le=90),
    categories: str = Query("", description="Optional comma filter"),
):
    """Risk-calendar events around today, grouped by date."""
    cat_list = [c.strip() for c in categories.split(",") if c.strip()]
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        cat_filter = ""
        params: list = [f"-{days_back} days", f"+{days_ahead} days"]
        if cat_list:
            cat_filter = f"AND category IN ({','.join('?' for _ in cat_list)})"
            params.extend(cat_list)
        rows = conn.execute(f"""
            SELECT event_date, category, title, country, symbol, detail
            FROM market_events
            WHERE event_date >= date('now', ?) AND event_date <= date('now', ?)
            {cat_filter}
            ORDER BY event_date ASC, category ASC, title ASC
        """, params).fetchall()

        by_date: dict = {}
        for r in rows:
            by_date.setdefault(r["event_date"], []).append({
                "category": r["category"], "title": r["title"],
                "country": r["country"], "symbol": r["symbol"],
                "detail": r["detail"],
            })
        logger.info("GET /api/macro/events — %d events, %.3fs", len(rows), time.time() - t0)
        return {
            "days": [{"date": d, "events": evs} for d, evs in sorted(by_date.items())],
            "total": len(rows),
        }
    finally:
        conn.close()
