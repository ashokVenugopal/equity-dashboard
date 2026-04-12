"""
Fund Flow API endpoints.

FII/DII/MF cash flow data: daily breakdown, monthly aggregates, period summaries.
Supports both simple view and Trendlyne-style detailed view with multiple segment tabs.
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fundflow", tags=["fundflow"])


@router.get("/summary")
def fundflow_summary():
    """Summary cards: FII/DII net values for key periods."""
    logger.info("GET /api/fundflow/summary")
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        latest = conn.execute("""
            SELECT participant_type, net_value, buy_value, sell_value, flow_date
            FROM best_institutional_flows
            WHERE period_type = 'daily' AND segment = 'CASH'
              AND flow_date = (SELECT MAX(flow_date) FROM best_institutional_flows
                               WHERE period_type = 'daily' AND segment = 'CASH')
            ORDER BY participant_type
        """).fetchall()

        latest_date = latest[0]["flow_date"] if latest else None

        mtd = conn.execute("""
            SELECT participant_type, SUM(net_value) AS net_value,
                   SUM(buy_value) AS buy_value, SUM(sell_value) AS sell_value,
                   COUNT(*) AS trading_days
            FROM best_institutional_flows
            WHERE period_type = 'daily' AND segment = 'CASH'
              AND flow_date >= date('now', 'start of month')
            GROUP BY participant_type ORDER BY participant_type
        """).fetchall()

        ytd = conn.execute("""
            SELECT participant_type, SUM(net_value) AS net_value,
                   SUM(buy_value) AS buy_value, SUM(sell_value) AS sell_value
            FROM best_institutional_flows
            WHERE period_type = 'daily' AND segment = 'CASH'
              AND flow_date >= date('now', 'start of year')
            GROUP BY participant_type ORDER BY participant_type
        """).fetchall()

        elapsed = time.time() - t0
        logger.info("GET /api/fundflow/summary — %.3fs", elapsed)
        return {
            "latest_date": latest_date,
            "latest": [dict(r) for r in latest],
            "mtd": [dict(r) for r in mtd],
            "ytd": [dict(r) for r in ytd],
        }
    except Exception as e:
        logger.error("GET /api/fundflow/summary — failed: %s", e)
        raise
    finally:
        conn.close()


@router.get("/daily")
def fundflow_daily(
    segment: str = Query("CASH", description="CASH, CASH_EQUITY, CASH_DEBT"),
    limit: int = Query(30, ge=1, le=365),
):
    """Daily FII/DII flows for bar chart and table."""
    logger.info("GET /api/fundflow/daily — segment=%s, limit=%d", segment, limit)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            SELECT flow_date, participant_type, buy_value, sell_value, net_value
            FROM best_institutional_flows
            WHERE period_type = 'daily' AND segment = ?
            ORDER BY flow_date DESC
            LIMIT ?
        """, (segment, limit * 3)).fetchall()

        by_date: dict = {}
        for r in rows:
            date = r["flow_date"]
            if date not in by_date:
                by_date[date] = {"flow_date": date}
            pt = r["participant_type"].lower()
            by_date[date][f"{pt}_buy"] = r["buy_value"]
            by_date[date][f"{pt}_sell"] = r["sell_value"]
            by_date[date][f"{pt}_net"] = r["net_value"]

        result = sorted(by_date.values(), key=lambda x: x["flow_date"], reverse=True)[:limit]

        elapsed = time.time() - t0
        logger.info("GET /api/fundflow/daily — %d days, %.3fs", len(result), elapsed)
        return {"segment": segment, "flows": result}
    except Exception as e:
        logger.error("GET /api/fundflow/daily — failed: %s", e)
        raise
    finally:
        conn.close()


@router.get("/monthly")
def fundflow_monthly(
    segment: str = Query("CASH"),
    limit: int = Query(24, ge=1, le=120),
):
    """Monthly FII/DII flows."""
    logger.info("GET /api/fundflow/monthly — segment=%s, limit=%d", segment, limit)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            SELECT flow_date, participant_type, buy_value, sell_value, net_value
            FROM best_institutional_flows
            WHERE period_type = 'monthly' AND segment = ?
            ORDER BY flow_date DESC
            LIMIT ?
        """, (segment, limit * 3)).fetchall()

        by_date: dict = {}
        for r in rows:
            date = r["flow_date"]
            if date not in by_date:
                by_date[date] = {"flow_date": date}
            pt = r["participant_type"].lower()
            by_date[date][f"{pt}_net"] = r["net_value"]
            by_date[date][f"{pt}_buy"] = r["buy_value"]
            by_date[date][f"{pt}_sell"] = r["sell_value"]

        result = sorted(by_date.values(), key=lambda x: x["flow_date"], reverse=True)[:limit]

        elapsed = time.time() - t0
        logger.info("GET /api/fundflow/monthly — %d months, %.3fs", len(result), elapsed)
        return {"segment": segment, "flows": result}
    except Exception as e:
        logger.error("GET /api/fundflow/monthly — failed: %s", e)
        raise
    finally:
        conn.close()


@router.get("/yearly")
def fundflow_yearly(
    segment: str = Query("SUMMARY_TOTAL"),
):
    """Yearly FII/DII/MF flows — Summary view."""
    logger.info("GET /api/fundflow/yearly — segment=%s", segment)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        rows = conn.execute("""
            SELECT flow_date, participant_type, segment, buy_value, sell_value, net_value
            FROM best_institutional_flows
            WHERE period_type = 'yearly'
            ORDER BY flow_date DESC, participant_type, segment
        """).fetchall()

        # Pivot by year with all segments
        by_year: dict = {}
        for r in rows:
            yr = r["flow_date"]
            if yr not in by_year:
                by_year[yr] = {"flow_date": yr}
            pt = r["participant_type"].lower()
            seg = r["segment"].lower()
            by_year[yr][f"{pt}_{seg}"] = r["net_value"]

        result = sorted(by_year.values(), key=lambda x: x["flow_date"], reverse=True)

        elapsed = time.time() - t0
        logger.info("GET /api/fundflow/yearly — %d years, %.3fs", len(result), elapsed)
        return {"flows": result}
    except Exception as e:
        logger.error("GET /api/fundflow/yearly — failed: %s", e)
        raise
    finally:
        conn.close()


@router.get("/detailed")
def fundflow_detailed(
    timeframe: str = Query("daily", description="daily, monthly, yearly"),
    view: str = Query("cash_provisional", description="summary, cash_provisional, fii_cash, fii_fo, mf_cash, mf_fo"),
    fo_sub: Optional[str] = Query(None, description="index or stock (for F&O views)"),
    limit: int = Query(30, ge=1, le=365),
):
    """
    Trendlyne-style detailed fund flow data.
    Returns rows pivoted by the selected view with appropriate columns.
    Includes aggregation rows (Last 30 Days, Last 2 Weeks, Last 1 Week) for daily timeframe.
    """
    logger.info("GET /api/fundflow/detailed — timeframe=%s, view=%s, fo_sub=%s", timeframe, view, fo_sub)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        # Map view to segments + participant types
        segment_map = {
            "summary": {"segments": ["SUMMARY_EQUITY", "SUMMARY_DEBT", "SUMMARY_DERIVATIVES", "SUMMARY_TOTAL"], "participants": ["FII", "MF"]},
            "cash_provisional": {"segments": ["CASH"], "participants": ["FII", "DII"]},
            "fii_cash": {"segments": ["CASH_EQUITY", "CASH_DEBT"], "participants": ["FII"]},
            "fii_fo": {"segments": [f"FO_{'INDEX' if fo_sub == 'index' else 'STOCK'}_FUTURES", f"FO_{'INDEX' if fo_sub == 'index' else 'STOCK'}_OPTIONS"] if fo_sub else ["FO_INDEX_FUTURES", "FO_INDEX_OPTIONS"], "participants": ["FII"]},
            "mf_cash": {"segments": ["CASH_EQUITY", "CASH_DEBT"], "participants": ["MF", "DII"]},
            "mf_fo": {"segments": [f"FO_{'INDEX' if fo_sub == 'index' else 'STOCK'}_FUTURES", f"FO_{'INDEX' if fo_sub == 'index' else 'STOCK'}_OPTIONS"] if fo_sub else ["FO_INDEX_FUTURES", "FO_INDEX_OPTIONS"], "participants": ["MF", "DII"]},
        }

        config = segment_map.get(view, segment_map["cash_provisional"])
        seg_placeholders = ",".join("?" * len(config["segments"]))
        pt_placeholders = ",".join("?" * len(config["participants"]))

        rows = conn.execute(f"""
            SELECT flow_date, participant_type, segment, buy_value, sell_value, net_value
            FROM best_institutional_flows
            WHERE period_type = ?
              AND segment IN ({seg_placeholders})
              AND participant_type IN ({pt_placeholders})
            ORDER BY flow_date DESC
        """, [timeframe] + config["segments"] + config["participants"]).fetchall()

        # Pivot by date
        by_date: dict = {}
        for r in rows:
            date = r["flow_date"]
            if date not in by_date:
                by_date[date] = {"flow_date": date}
            pt = r["participant_type"].lower()
            seg_short = r["segment"].lower().replace("cash_", "").replace("fo_", "").replace("summary_", "")
            by_date[date][f"{pt}_{seg_short}_buy"] = r["buy_value"]
            by_date[date][f"{pt}_{seg_short}_sell"] = r["sell_value"]
            by_date[date][f"{pt}_{seg_short}_net"] = r["net_value"]

        result = sorted(by_date.values(), key=lambda x: x["flow_date"], reverse=True)[:limit]

        # For daily timeframe, compute aggregation rows
        aggregations = []
        if timeframe == "daily" and result:
            all_dates = sorted(by_date.keys(), reverse=True)
            for label, days in [("Last 30 Days", 30), ("Last 2 Weeks", 14), ("Last 1 Week", 7)]:
                cutoff_dates = all_dates[:days]
                if not cutoff_dates:
                    continue
                agg: dict = {"flow_date": label, "_is_aggregation": True}
                for d in cutoff_dates:
                    row = by_date[d]
                    for k, v in row.items():
                        if k != "flow_date" and isinstance(v, (int, float)) and v is not None:
                            agg[k] = round((agg.get(k) or 0) + v, 2)
                aggregations.append(agg)

        elapsed = time.time() - t0
        logger.info("GET /api/fundflow/detailed — %d rows, %d aggregations, %.3fs", len(result), len(aggregations), elapsed)
        return {
            "timeframe": timeframe,
            "view": view,
            "aggregations": aggregations,
            "rows": result,
        }
    except Exception as e:
        logger.error("GET /api/fundflow/detailed — failed: %s", e)
        raise
    finally:
        conn.close()
