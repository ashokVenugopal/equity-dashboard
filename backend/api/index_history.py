"""
Index history API: multi-instrument overlay series, range stats
(52W / 3Y / all-time high-low), and equal-weight classification baskets.

Powers the /indices dashboard page: compare standard indices (India +
global), stocks (pair comparison for portfolio building), and custom
indices built from classification groups (themes, niche indices, sectors).
"""
import json
import logging
import re
import time
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from backend.core.connection import get_observations_connection, get_pipeline_connection

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
            base = pts[0][1] if pts else None
            if normalize and pts:
                data = [{"time": d, "value": round(v / base * 100.0, 2)} for d, v in pts]
            else:
                data = [{"time": d, "value": v} for d, v in pts]
            out.append({
                "symbol": inst["symbol"], "name": inst["name"],
                "instrument_type": inst["instrument_type"],
                # Base close used for rebasing — lets the client convert
                # absolute price levels (e.g. VAH/VAL) into rebased units.
                "base": base,
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



def _equal_weight_series(conn, instrument_ids, range_days, min_floor: int = 3):
    """Equal-weight basket: each instrument rebased to 100 at its first
    date in the window; daily value = mean across instruments with data
    that day (at least max(min_floor, used/2) reporting)."""
    rebased_by_day: dict = {}
    counted = 0
    for iid in instrument_ids:
        pts = _series_for_instrument(conn, iid, range_days)
        if len(pts) < 30:
            continue
        counted += 1
        base = pts[0][1]
        for d, v in pts:
            rebased_by_day.setdefault(d, []).append(v / base * 100.0)

    min_members = max(min_floor, counted // 2)
    points = [
        {"time": d, "value": round(sum(vals) / len(vals), 2)}
        for d, vals in sorted(rebased_by_day.items())
        if len(vals) >= min_members
    ]
    return points, counted


# ── User-defined custom indices (stored in the observations DB) ──

def _validate_custom_payload(name: str, symbols: list) -> tuple:
    name = (name or "").strip()
    if not name or len(name) > 60 or not re.match(r"^[\w .&/-]+$", name):
        raise HTTPException(status_code=400, detail="Invalid name (1-60 chars, alphanumeric/space/.&/-)")
    if not isinstance(symbols, list) or not (2 <= len(symbols) <= 50):
        raise HTTPException(status_code=400, detail="Need 2-50 symbols")
    cleaned = sorted({str(s).strip().upper() for s in symbols if str(s).strip()})
    if len(cleaned) < 2:
        raise HTTPException(status_code=400, detail="Need 2-50 distinct symbols")
    return name, cleaned


@router.get("/custom")
def list_custom_indices():
    """All user-defined custom indices."""
    conn = get_observations_connection()
    try:
        rows = conn.execute(
            "SELECT custom_index_id, name, symbols_json, updated_at "
            "FROM custom_indices ORDER BY name").fetchall()
        return {"custom_indices": [
            {"id": r["custom_index_id"], "name": r["name"],
             "symbols": json.loads(r["symbols_json"]),
             "updated_at": r["updated_at"]}
            for r in rows
        ]}
    finally:
        conn.close()


@router.post("/custom")
def create_custom_index(payload: dict = Body(...)):
    name, symbols = _validate_custom_payload(
        payload.get("name", ""), payload.get("symbols", []))
    # Validate symbols exist in the pipeline universe
    pconn = get_pipeline_connection()
    try:
        known = {r["symbol"] for r in pconn.execute(
            "SELECT symbol FROM instruments WHERE is_active = 1")}
    finally:
        pconn.close()
    unknown = [s for s in symbols if s not in known]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown symbols: {', '.join(unknown[:5])}")

    conn = get_observations_connection()
    try:
        try:
            cur = conn.execute(
                "INSERT INTO custom_indices (name, symbols_json) VALUES (?, ?)",
                (name, json.dumps(symbols)))
            conn.commit()
        except Exception as exc:
            if "UNIQUE" in str(exc):
                raise HTTPException(status_code=409, detail=f"'{name}' already exists")
            raise
        logger.info("POST /api/index-history/custom — created '%s' (%d symbols)",
                    name, len(symbols))
        return {"id": cur.lastrowid, "name": name, "symbols": symbols}
    finally:
        conn.close()


@router.put("/custom/{custom_id}")
def update_custom_index(custom_id: int, payload: dict = Body(...)):
    name, symbols = _validate_custom_payload(
        payload.get("name", ""), payload.get("symbols", []))
    conn = get_observations_connection()
    try:
        cur = conn.execute(
            "UPDATE custom_indices SET name = ?, symbols_json = ?, "
            "updated_at = datetime('now') WHERE custom_index_id = ?",
            (name, json.dumps(symbols), custom_id))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Custom index not found")
        return {"id": custom_id, "name": name, "symbols": symbols}
    finally:
        conn.close()


@router.delete("/custom/{custom_id}")
def delete_custom_index(custom_id: int):
    conn = get_observations_connection()
    try:
        cur = conn.execute(
            "DELETE FROM custom_indices WHERE custom_index_id = ?", (custom_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Custom index not found")
        return {"deleted": custom_id}
    finally:
        conn.close()


@router.get("/custom/{custom_id}/series")
def custom_index_series(custom_id: int, range: str = Query("3y", pattern="^(1y|3y|5y|max)$")):
    """Equal-weight series for a user-defined custom index."""
    oconn = get_observations_connection()
    try:
        row = oconn.execute(
            "SELECT name, symbols_json FROM custom_indices WHERE custom_index_id = ?",
            (custom_id,)).fetchone()
    finally:
        oconn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Custom index not found")
    symbols = json.loads(row["symbols_json"])

    conn = get_pipeline_connection()
    try:
        ids = [r["instrument_id"] for r in conn.execute(
            f"SELECT instrument_id FROM instruments "
            f"WHERE symbol IN ({','.join('?' for _ in symbols)}) AND is_active = 1",
            symbols).fetchall()]
        points, counted = _equal_weight_series(conn, ids, _RANGE_DAYS[range], min_floor=2)
        return {"id": custom_id, "name": row["name"], "range": range,
                "members_used": counted, "points": points}
    finally:
        conn.close()



_VALUE_AREA_PCT = 0.70
_PROFILE_BINS = 60
_MIN_PROFILE_DAYS = 10


def _volume_profile(bars, bins: int = _PROFILE_BINS):
    """Composite volume profile from daily bars (approximation: each
    day's volume spread uniformly across its high-low range).

    Returns (poc, vah, val, total_volume) — the value area is grown
    outward from the POC by repeatedly taking the higher-volume adjacent
    bin until _VALUE_AREA_PCT of volume is enclosed (standard method).
    """
    lo = min(b[0] for b in bars)
    hi = max(b[1] for b in bars)
    if hi <= lo:
        return None
    width = (hi - lo) / bins
    vol = [0.0] * bins

    for b_lo, b_hi, b_vol in bars:
        if not b_vol:
            continue
        if b_hi <= b_lo:
            idx = min(int((b_lo - lo) / width), bins - 1)
            vol[idx] += b_vol
            continue
        start = max(0, min(int((b_lo - lo) / width), bins - 1))
        end = max(0, min(int((b_hi - lo) / width), bins - 1))
        share = b_vol / (end - start + 1)
        for i in range(start, end + 1):
            vol[i] += share

    total = sum(vol)
    if total <= 0:
        return None

    poc_idx = max(range(bins), key=lambda i: vol[i])
    lo_idx = hi_idx = poc_idx
    enclosed = vol[poc_idx]
    while enclosed < total * _VALUE_AREA_PCT and (lo_idx > 0 or hi_idx < bins - 1):
        below = vol[lo_idx - 1] if lo_idx > 0 else -1.0
        above = vol[hi_idx + 1] if hi_idx < bins - 1 else -1.0
        if above >= below:
            hi_idx += 1
            enclosed += vol[hi_idx]
        else:
            lo_idx -= 1
            enclosed += vol[lo_idx]

    center = lambda i: lo + (i + 0.5) * width
    return {
        "poc": round(center(poc_idx), 2),
        "vah": round(lo + (hi_idx + 1) * width, 2),
        "val": round(lo + lo_idx * width, 2),
        "total_volume": round(total),
    }


@router.get("/volume-profile")
def volume_profile(
    symbol: str = Query(...),
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
):
    """VAH / VAL / POC for a date window, from daily bars.

    APPROXIMATION: true value areas need intraday volume-at-price; with
    daily bars each day's volume is spread uniformly across its high-low
    range. Reasonable for multi-week windows; refused below
    _MIN_PROFILE_DAYS trading days.
    """
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        inst = _resolve_symbols(conn, [symbol])[0]
        rows = conn.execute("""
            SELECT low, high, volume FROM best_prices
            WHERE instrument_id = ? AND trade_date >= ? AND trade_date <= ?
              AND low IS NOT NULL AND high IS NOT NULL
            ORDER BY trade_date ASC
        """, (inst["instrument_id"], date_from, date_to)).fetchall()
        bars = [(r["low"], r["high"], r["volume"] or 0) for r in rows]
        with_vol = [b for b in bars if b[2] > 0]

        if len(with_vol) < _MIN_PROFILE_DAYS:
            return {"symbol": inst["symbol"], "available": False,
                    "reason": f"needs >= {_MIN_PROFILE_DAYS} trading days with volume "
                              f"(got {len(with_vol)})"}
        profile = _volume_profile(with_vol)
        if profile is None:
            return {"symbol": inst["symbol"], "available": False,
                    "reason": "degenerate price range"}
        logger.info("GET /api/index-history/volume-profile %s %s→%s — %.3fs",
                    symbol, date_from, date_to, time.time() - t0)
        return {"symbol": inst["symbol"], "available": True,
                "from": date_from, "to": date_to, "days": len(with_vol),
                "approx": True, **profile}
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

        points, counted = _equal_weight_series(
            conn, [m["instrument_id"] for m in members], _RANGE_DAYS[range])
        logger.info("GET /api/index-history/basket %s:%s — %d members, %.3fs",
                    classification_type, name, counted, time.time() - t0)
        return {
            "classification_type": classification_type, "name": name,
            "range": range, "members_used": counted, "points": points,
        }
    finally:
        conn.close()
