"""Health check and data freshness endpoints."""
import logging
import time

from fastapi import APIRouter

from backend.core.connection import get_observations_connection, get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/api/data-freshness")
def data_freshness():
    """
    Returns timestamps for the most recent valid data across market and fundamental sources.
    Used by the frontend to show data staleness warnings.
    """
    logger.info("GET /api/data-freshness")
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        row = conn.execute("""
            SELECT
                (SELECT MAX(trade_date) FROM market_breadth
                 WHERE (advances + declines) > 0) AS last_trading_day,
                (SELECT MAX(trade_date) FROM price_history
                 WHERE source IN ('nse_bhavcopy', 'bse_bhavcopy')) AS last_price_ingest,
                (SELECT MAX(trade_date) FROM price_history
                 WHERE source = 'nse_index') AS last_index_price,
                (SELECT MAX(ingested_at) FROM sources
                 WHERE file_type IN ('screener_excel', 'screener_web')) AS last_fundamental_ingest,
                (SELECT MAX(flow_date) FROM institutional_flows
                 WHERE period_type = 'daily') AS last_flow_date
        """).fetchone()

        result = {
            "last_trading_day": row["last_trading_day"],
            "last_price_ingest": row["last_price_ingest"],
            "last_index_price": row["last_index_price"],
            "last_fundamental_ingest": row["last_fundamental_ingest"],
            "last_flow_date": row["last_flow_date"],
        }
        elapsed = time.time() - t0
        logger.info("GET /api/data-freshness — %.3fs", elapsed)
        return result
    except Exception as e:
        logger.error("GET /api/data-freshness — failed: %s", e)
        return {
            "last_trading_day": None, "last_price_ingest": None,
            "last_index_price": None, "last_fundamental_ingest": None,
            "last_flow_date": None,
        }
    finally:
        conn.close()


@router.get("/api/health")
def health_check():
    """Health check with database stats."""
    logger.info("GET /api/health — checking databases...")
    t0 = time.time()
    result = {"status": "ok", "pipeline_db": None, "observations_db": None}
    errors = []

    try:
        conn = get_pipeline_connection()
        stats = {}
        for table in ["companies", "facts", "price_history", "instruments", "classifications",
                       "institutional_flows", "derived_technicals", "market_breadth"]:
            try:
                row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
                stats[table] = row["cnt"]
            except Exception as e:
                logger.error("Health check — failed to count table %s: %s", table, e)
                stats[table] = "error"
                errors.append(f"pipeline.{table}")
        result["pipeline_db"] = {"connected": True, "tables": stats}
        conn.close()
    except Exception as e:
        logger.error("Health check — pipeline DB connection failed: %s", e)
        result["pipeline_db"] = {"connected": False, "error": str(e)}
        errors.append("pipeline_connection")

    try:
        conn = get_observations_connection()
        row = conn.execute("SELECT COUNT(*) as cnt FROM observations").fetchone()
        result["observations_db"] = {"connected": True, "observations_count": row["cnt"]}
        conn.close()
    except Exception as e:
        logger.error("Health check — observations DB connection failed: %s", e)
        result["observations_db"] = {"connected": False, "error": str(e)}
        errors.append("observations_connection")

    elapsed = time.time() - t0
    result["response_time_ms"] = round(elapsed * 1000, 1)
    logger.info(
        "GET /api/health — %d errors, %.3fs%s",
        len(errors), elapsed,
        f" [failed: {', '.join(errors)}]" if errors else "",
    )
    return result
