"""
Investors API: superstar-shareholder portfolios (Trendlyne-sourced).

Data: pipeline DB investor_holdings — one row per (investor, stock,
quarter-end) with holding %. NULL pct means 'not disclosed' (below the
1% disclosure threshold, not yet filed, or not held) — change
classification treats >0 → NULL as an exit/below-threshold event.

Groups (user-defined, related/coordinating investors) live in the
writable observations DB.
"""
import json
import logging
import re
import time
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from backend.core.connection import get_observations_connection, get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/investors", tags=["investors"])

_GROUPS_SCHEMA = """
CREATE TABLE IF NOT EXISTS investor_groups (
    group_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    member_ids_json TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _oconn():
    conn = get_observations_connection()
    conn.executescript(_GROUPS_SCHEMA)
    return conn


def _quarters(conn, limit: int = 12) -> List[str]:
    return [r["quarter_end"] for r in conn.execute(
        "SELECT DISTINCT quarter_end FROM investor_holdings "
        "ORDER BY quarter_end DESC LIMIT ?", (limit,))]


def classify_change(prev: Optional[float], cur: Optional[float],
                    threshold: float = 0.05) -> Optional[str]:
    """Transition between two quarters' holding %.

    new   — undisclosed → disclosed
    exit  — disclosed → undisclosed/zero (sold OR fell below the 1%
            disclosure threshold; the data cannot distinguish)
    add   — disclosed both, up by > threshold
    trim  — disclosed both, down by > threshold
    None  — no material change / both undisclosed
    """
    p = prev if prev and prev > 0 else None
    c = cur if cur and cur > 0 else None
    if p is None and c is not None:
        return "new"
    if p is not None and c is None:
        return "exit"
    if p is not None and c is not None:
        if c - p > threshold:
            return "add"
        if p - c > threshold:
            return "trim"
    return None


@router.get("/list")
def investors_list(category: str = Query("", description="individual|fii|institutional")):
    """Investor registry with latest-quarter activity counts."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        quarters = _quarters(conn, 2)
        if not quarters:
            return {"investors": [], "quarters": []}
        latest = quarters[0]
        prev = quarters[1] if len(quarters) > 1 else None

        cat_filter = "AND i.categories LIKE ?" if category else ""
        params = [f"%{category}%"] if category else []
        rows = conn.execute(f"""
            SELECT i.investor_id, i.trendlyne_id, i.name, i.slug, i.categories,
                   COUNT(DISTINCT CASE WHEN h.quarter_end = ? AND h.holding_pct > 0
                                       THEN h.trendlyne_stock_pk END) AS holdings_latest
            FROM investors i
            LEFT JOIN investor_holdings h ON h.investor_id = i.investor_id
            WHERE 1=1 {cat_filter}
            GROUP BY i.investor_id
            ORDER BY i.name
        """, [latest] + params).fetchall()

        # Per-investor changes in the latest quarter
        changes: dict = {}
        if prev:
            change_rows = conn.execute("""
                SELECT investor_id, trendlyne_stock_pk,
                       MAX(CASE WHEN quarter_end = ? THEN holding_pct END) AS prev_pct,
                       MAX(CASE WHEN quarter_end = ? THEN holding_pct END) AS cur_pct
                FROM investor_holdings
                WHERE quarter_end IN (?, ?)
                GROUP BY investor_id, trendlyne_stock_pk
            """, (prev, latest, prev, latest)).fetchall()
            # Shareholding filings trickle in for ~6 weeks after quarter
            # end, per COMPANY. A >0 → NULL transition is only a real
            # exit if that stock's latest-quarter data has been published
            # — i.e. someone discloses a holding in it this quarter.
            # Without this gate we saw 300+ phantom exits per institution.
            stock_filed = {r["trendlyne_stock_pk"] for r in change_rows
                           if r["cur_pct"] and r["cur_pct"] > 0}
            for r in change_rows:
                kind = classify_change(r["prev_pct"], r["cur_pct"])
                if kind == "exit" and r["trendlyne_stock_pk"] not in stock_filed:
                    continue
                if kind:
                    d = changes.setdefault(r["investor_id"],
                                           {"new": 0, "exit": 0, "add": 0, "trim": 0})
                    d[kind] += 1

        out = []
        for r in rows:
            out.append({
                "id": r["investor_id"], "trendlyne_id": r["trendlyne_id"],
                "name": r["name"], "slug": r["slug"],
                "categories": r["categories"].split(","),
                "holdings_latest": r["holdings_latest"],
                "changes_latest": changes.get(r["investor_id"],
                                              {"new": 0, "exit": 0, "add": 0, "trim": 0}),
            })
        logger.info("GET /api/investors/list — %d, %.3fs", len(out), time.time() - t0)
        return {"investors": out, "quarters": quarters}
    finally:
        conn.close()


@router.get("/changes")
def investor_changes(
    quarter: str = Query("", description="ISO quarter end; default latest"),
    kind: str = Query("", pattern="^(new|exit|add|trim)?$"),
    category: str = Query(""),
):
    """All (investor, stock) changes for a quarter vs the prior quarter."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        quarters = _quarters(conn)
        if len(quarters) < 2:
            return {"changes": [], "quarter": None, "quarters": quarters}
        latest = quarter if quarter in quarters else quarters[0]
        idx = quarters.index(latest)
        if idx + 1 >= len(quarters):
            return {"changes": [], "quarter": latest, "quarters": quarters}
        prior = quarters[idx + 1]

        rows = conn.execute("""
            SELECT h.investor_id, h.trendlyne_stock_pk, i.name AS investor,
                   i.categories, h.stock_name, h.nse_code, h.company_id,
                   MAX(CASE WHEN h.quarter_end = ? THEN h.holding_pct END) AS prev_pct,
                   MAX(CASE WHEN h.quarter_end = ? THEN h.holding_pct END) AS cur_pct
            FROM investor_holdings h
            JOIN investors i ON i.investor_id = h.investor_id
            WHERE h.quarter_end IN (?, ?)
            GROUP BY h.investor_id, h.trendlyne_stock_pk
        """, (prior, latest, prior, latest)).fetchall()

        # sector lookup for matched companies
        sectors = {r["company_id"]: r["classification_name"] for r in conn.execute("""
            SELECT DISTINCT i.company_id, cl.classification_name
            FROM classifications cl
            JOIN instruments i ON cl.instrument_id = i.instrument_id
            WHERE cl.classification_type = 'sector'
              AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
              AND i.company_id IS NOT NULL
        """)}

        # Per-stock filing gate — see investors_list for rationale.
        stock_filed = {r["trendlyne_stock_pk"] for r in rows
                       if r["cur_pct"] and r["cur_pct"] > 0}
        out = []
        for r in rows:
            k = classify_change(r["prev_pct"], r["cur_pct"])
            if k == "exit" and r["trendlyne_stock_pk"] not in stock_filed:
                continue
            if not k or (kind and k != kind):
                continue
            if category and category not in (r["categories"] or ""):
                continue
            out.append({
                "investor_id": r["investor_id"], "investor": r["investor"],
                "categories": (r["categories"] or "").split(","),
                "stock_name": r["stock_name"], "nse_code": r["nse_code"],
                "tracked": r["company_id"] is not None,
                "sector": sectors.get(r["company_id"]),
                "kind": k,
                "prev_pct": r["prev_pct"], "cur_pct": r["cur_pct"],
                "delta": round((r["cur_pct"] or 0) - (r["prev_pct"] or 0), 2),
            })
        out.sort(key=lambda x: (x["kind"], -(abs(x["delta"]))))
        logger.info("GET /api/investors/changes %s — %d, %.3fs",
                    latest, len(out), time.time() - t0)
        return {"changes": out, "quarter": latest, "prior": prior, "quarters": quarters}
    finally:
        conn.close()


@router.get("/matrix")
def investor_matrix(
    by: str = Query("sector", pattern="^(sector|stock)$"),
    quarters_count: int = Query(8, ge=2, le=24),
    category: str = Query(""),
    min_pct: float = Query(0.0, ge=0.0),
):
    """Radar-style matrix: rows = sector or stock, columns = quarters,
    cells = investors holding (alphabetical, pct in brackets, change flag).

    Sector rows cover only stocks matched to the tracked universe (sector
    comes from our classifications); stock rows cover everything.
    """
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        quarters = _quarters(conn, quarters_count)
        if not quarters:
            return {"rows": [], "quarters": []}
        qmarks = ",".join("?" for _ in quarters)

        cat_filter = "AND i.categories LIKE ?" if category else ""
        params: list = list(quarters) + ([f"%{category}%"] if category else [])

        rows = conn.execute(f"""
            SELECT h.quarter_end, h.stock_name, h.nse_code, h.company_id,
                   h.holding_pct, i.name AS investor, h.investor_id,
                   h.trendlyne_stock_pk
            FROM investor_holdings h
            JOIN investors i ON i.investor_id = h.investor_id
            WHERE h.quarter_end IN ({qmarks}) AND h.holding_pct > 0 {cat_filter}
        """, params).fetchall()

        sectors = {r["company_id"]: r["classification_name"] for r in conn.execute("""
            SELECT DISTINCT i.company_id, cl.classification_name
            FROM classifications cl
            JOIN instruments i ON cl.instrument_id = i.instrument_id
            WHERE cl.classification_type = 'sector'
              AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
              AND i.company_id IS NOT NULL
        """)}

        # Previous-quarter pct per (investor, stock) for change flags
        by_key: dict = {}
        for r in rows:
            by_key[(r["investor_id"], r["trendlyne_stock_pk"], r["quarter_end"])] = r["holding_pct"]

        cells: dict = {}
        for r in rows:
            if r["holding_pct"] < min_pct:
                continue
            if by == "sector":
                row_key = sectors.get(r["company_id"])
                if row_key is None:
                    continue  # untracked stocks have no sector
            else:
                row_key = r["stock_name"]
            qi = quarters.index(r["quarter_end"])
            prev_q = quarters[qi + 1] if qi + 1 < len(quarters) else None
            prev = (by_key.get((r["investor_id"], r["trendlyne_stock_pk"], prev_q))
                    if prev_q else None)
            flag = classify_change(prev, r["holding_pct"]) if prev_q else None
            cells.setdefault(row_key, {}).setdefault(r["quarter_end"], []).append({
                "investor": r["investor"], "investor_id": r["investor_id"],
                "pct": r["holding_pct"], "flag": flag,
                "stock": r["stock_name"] if by == "sector" else None,
            })

        out_rows = []
        for row_key in sorted(cells):
            qcells = {}
            for q, entries in cells[row_key].items():
                # Alphabetical per cell (stable position across quarters)
                entries.sort(key=lambda e: e["investor"].lower())
                qcells[q] = entries
            out_rows.append({"row": row_key, "cells": qcells})

        logger.info("GET /api/investors/matrix by=%s — %d rows, %.3fs",
                    by, len(out_rows), time.time() - t0)
        return {"rows": out_rows, "quarters": quarters, "by": by}
    finally:
        conn.close()


@router.get("/missing-companies")
def missing_companies():
    """Stocks held by tracked investors but absent from our companies
    universe — the import wishlist, ranked by holder interest."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        latest = (_quarters(conn, 1) or [None])[0]
        rows = conn.execute("""
            SELECT h.stock_name, h.nse_code,
                   COUNT(DISTINCT h.investor_id) AS holders,
                   MAX(h.quarter_end) AS last_seen,
                   SUM(CASE WHEN h.quarter_end = ? AND h.holding_pct > 0
                       THEN 1 ELSE 0 END) AS holders_latest
            FROM investor_holdings h
            WHERE h.company_id IS NULL
            GROUP BY h.trendlyne_stock_pk
            ORDER BY holders_latest DESC, holders DESC
        """, (latest,)).fetchall()
        logger.info("GET /api/investors/missing-companies — %d, %.3fs",
                    len(rows), time.time() - t0)
        return {"missing": [dict(r) for r in rows], "latest_quarter": latest}
    finally:
        conn.close()


@router.get("/{investor_id}/holdings")
def investor_holdings(investor_id: int):
    """One investor's full holdings pivot: stocks × quarters."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        inv = conn.execute(
            "SELECT investor_id, name, slug, categories FROM investors "
            "WHERE investor_id = ?", (investor_id,)).fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Investor not found")
        quarters = _quarters(conn)
        rows = conn.execute("""
            SELECT trendlyne_stock_pk, stock_name, nse_code, company_id,
                   quarter_end, holding_pct
            FROM investor_holdings WHERE investor_id = ?
            ORDER BY stock_name, quarter_end DESC
        """, (investor_id,)).fetchall()
        stocks: dict = {}
        for r in rows:
            s = stocks.setdefault(r["trendlyne_stock_pk"], {
                "stock_name": r["stock_name"], "nse_code": r["nse_code"],
                "tracked": r["company_id"] is not None, "quarters": {},
            })
            s["quarters"][r["quarter_end"]] = r["holding_pct"]
        # Latest-quarter change flag per stock
        out = []
        for s in stocks.values():
            if len(quarters) >= 2:
                s["latest_change"] = classify_change(
                    s["quarters"].get(quarters[1]), s["quarters"].get(quarters[0]))
            else:
                s["latest_change"] = None
            out.append(s)
        out.sort(key=lambda s: (s["quarters"].get(quarters[0]) or 0), reverse=True)
        logger.info("GET /api/investors/%d/holdings — %d stocks, %.3fs",
                    investor_id, len(out), time.time() - t0)
        return {"investor": dict(inv), "quarters": quarters, "holdings": out}
    finally:
        conn.close()


# ── Groups (observations DB) ──

def _validate_group(name: str, member_ids: list) -> tuple:
    name = (name or "").strip()
    if not name or len(name) > 60 or not re.match(r"^[\w .&/-]+$", name):
        raise HTTPException(status_code=400, detail="Invalid group name")
    if not isinstance(member_ids, list) or len(member_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 members")
    ids = sorted({int(m) for m in member_ids})
    return name, ids


@router.get("/groups")
def list_groups():
    conn = _oconn()
    try:
        rows = conn.execute(
            "SELECT group_id, name, member_ids_json FROM investor_groups ORDER BY name"
        ).fetchall()
        return {"groups": [
            {"id": r["group_id"], "name": r["name"],
             "member_ids": json.loads(r["member_ids_json"])}
            for r in rows]}
    finally:
        conn.close()


@router.post("/groups")
def create_group(payload: dict = Body(...)):
    name, ids = _validate_group(payload.get("name", ""), payload.get("member_ids", []))
    conn = _oconn()
    try:
        try:
            cur = conn.execute(
                "INSERT INTO investor_groups (name, member_ids_json) VALUES (?, ?)",
                (name, json.dumps(ids)))
            conn.commit()
        except Exception as exc:
            if "UNIQUE" in str(exc):
                raise HTTPException(status_code=409, detail=f"'{name}' already exists")
            raise
        return {"id": cur.lastrowid, "name": name, "member_ids": ids}
    finally:
        conn.close()


@router.put("/groups/{group_id}")
def update_group(group_id: int, payload: dict = Body(...)):
    name, ids = _validate_group(payload.get("name", ""), payload.get("member_ids", []))
    conn = _oconn()
    try:
        cur = conn.execute(
            "UPDATE investor_groups SET name=?, member_ids_json=?, "
            "updated_at=datetime('now') WHERE group_id=?",
            (name, json.dumps(ids), group_id))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Group not found")
        return {"id": group_id, "name": name, "member_ids": ids}
    finally:
        conn.close()


@router.delete("/groups/{group_id}")
def delete_group(group_id: int):
    conn = _oconn()
    try:
        cur = conn.execute(
            "DELETE FROM investor_groups WHERE group_id=?", (group_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Group not found")
        return {"deleted": group_id}
    finally:
        conn.close()


@router.get("/groups/{group_id}/holdings")
def group_holdings(
    group_id: int,
    mode: str = Query("consolidated", pattern="^(consolidated|overlap)$"),
):
    """Group view across members.

    consolidated — every stock any member holds; per-quarter pct = SUM of
    members' pcts (a coordination-size proxy), plus per-member breakdown.
    overlap — only stocks held by >= 2 members in the latest quarter.
    """
    oconn = _oconn()
    try:
        row = oconn.execute(
            "SELECT name, member_ids_json FROM investor_groups WHERE group_id=?",
            (group_id,)).fetchone()
    finally:
        oconn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Group not found")
    member_ids = json.loads(row["member_ids_json"])

    conn = get_pipeline_connection()
    try:
        quarters = _quarters(conn)
        marks = ",".join("?" for _ in member_ids)
        rows = conn.execute(f"""
            SELECT h.trendlyne_stock_pk, h.stock_name, h.nse_code, h.company_id,
                   h.quarter_end, h.holding_pct, i.name AS investor
            FROM investor_holdings h
            JOIN investors i ON i.investor_id = h.investor_id
            WHERE h.investor_id IN ({marks})
        """, member_ids).fetchall()

        stocks: dict = {}
        for r in rows:
            s = stocks.setdefault(r["trendlyne_stock_pk"], {
                "stock_name": r["stock_name"], "nse_code": r["nse_code"],
                "tracked": r["company_id"] is not None,
                "quarters": {}, "members": {},
            })
            if r["holding_pct"] is not None and r["holding_pct"] > 0:
                s["quarters"][r["quarter_end"]] = round(
                    s["quarters"].get(r["quarter_end"], 0.0) + r["holding_pct"], 2)
                s["members"].setdefault(r["investor"], {})[r["quarter_end"]] = r["holding_pct"]

        latest = quarters[0] if quarters else None
        out = []
        for s in stocks.values():
            holders_latest = sum(
                1 for m in s["members"].values() if m.get(latest, 0) > 0) if latest else 0
            s["holders_latest"] = holders_latest
            if mode == "overlap" and holders_latest < 2:
                continue
            out.append(s)
        out.sort(key=lambda s: (s["holders_latest"],
                                s["quarters"].get(latest, 0) if latest else 0),
                 reverse=True)
        return {"group": row["name"], "mode": mode, "member_ids": member_ids,
                "quarters": quarters, "holdings": out}
    finally:
        conn.close()
