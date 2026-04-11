"""Health check endpoint with DB stats."""
import logging
import time

from fastapi import APIRouter

from backend.core.connection import get_observations_connection, get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health_check():
    """Health check with database stats."""
    t0 = time.time()
    result = {"status": "ok", "pipeline_db": None, "observations_db": None}

    try:
        conn = get_pipeline_connection()
        stats = {}
        for table in ["companies", "facts", "price_history", "instruments", "classifications",
                       "institutional_flows", "derived_technicals", "market_breadth"]:
            try:
                row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
                stats[table] = row["cnt"]
            except Exception:
                stats[table] = "error"
        result["pipeline_db"] = {"connected": True, "tables": stats}
        conn.close()
    except Exception as e:
        result["pipeline_db"] = {"connected": False, "error": str(e)}

    try:
        conn = get_observations_connection()
        row = conn.execute("SELECT COUNT(*) as cnt FROM observations").fetchone()
        result["observations_db"] = {"connected": True, "observations_count": row["cnt"]}
        conn.close()
    except Exception as e:
        result["observations_db"] = {"connected": False, "error": str(e)}

    elapsed = time.time() - t0
    result["response_time_ms"] = round(elapsed * 1000, 1)
    logger.info("GET /api/health — %.3fs", elapsed)
    return result
