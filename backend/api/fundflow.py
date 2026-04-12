"""
Fund Flow API endpoints.

FII/DII/MF cash flow data: daily breakdown, monthly aggregates, period summaries.
Trendlyne-style layout: summary cards + daily bar chart + table.
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
    """
    Summary cards: FII/DII net values for key periods.
    Returns latest day, MTD (month-to-date), YTD (year-to-date), and last 3 months.
    """
    logger.info("GET /api/fundflow/summary")
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        # Latest daily flows
        latest = conn.execute("""
            SELECT participant_type, net_value, buy_value, sell_value, flow_date
            FROM best_institutional_flows
            WHERE period_type = 'daily' AND segment = 'CASH'
              AND flow_date = (SELECT MAX(flow_date) FROM best_institutional_flows
                               WHERE period_type = 'daily' AND segment = 'CASH')
            ORDER BY participant_type
        """).fetchall()

        latest_date = latest[0]["flow_date"] if latest else None

        # Month-to-date (sum of daily CASH flows for current month)
        mtd = conn.execute("""
            SELECT participant_type,
                   SUM(net_value) AS net_value,
                   SUM(buy_value) AS buy_value,
                   SUM(sell_value) AS sell_value,
                   COUNT(*) AS trading_days
            FROM best_institutional_flows
            WHERE period_type = 'daily' AND segment = 'CASH'
              AND flow_date >= date('now', 'start of month')
            GROUP BY participant_type
            ORDER BY participant_type
        """).fetchall()

        # Previous month
        prev_month = conn.execute("""
            SELECT participant_type, net_value, flow_date
            FROM best_institutional_flows
            WHERE period_type = 'monthly' AND segment = 'CASH'
              AND flow_date = (
                  SELECT MAX(flow_date) FROM best_institutional_flows
                  WHERE period_type = 'monthly' AND segment = 'CASH'
                    AND flow_date < date('now', 'start of month')
              )
            ORDER BY participant_type
        """).fetchall()

        # YTD
        ytd = conn.execute("""
            SELECT participant_type,
                   SUM(net_value) AS net_value,
                   SUM(buy_value) AS buy_value,
                   SUM(sell_value) AS sell_value
            FROM best_institutional_flows
            WHERE period_type = 'daily' AND segment = 'CASH'
              AND flow_date >= date('now', 'start of year')
            GROUP BY participant_type
            ORDER BY participant_type
        """).fetchall()

        result = {
            "latest_date": latest_date,
            "latest": [dict(r) for r in latest],
            "mtd": [dict(r) for r in mtd],
            "prev_month": [dict(r) for r in prev_month],
            "ytd": [dict(r) for r in ytd],
        }

        elapsed = time.time() - t0
        logger.info("GET /api/fundflow/summary — %.3fs", elapsed)
        return result
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
        """, (segment, limit * 3)).fetchall()  # *3 because FII+DII+MF per date

        # Pivot: one row per date with FII/DII columns
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
