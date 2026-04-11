"""
Export API endpoints.

CSV export for any table query, observation export.
"""
import csv
import io
import json
import logging
import time

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from backend.core.connection import get_observations_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/observations")
def export_observations(
    format: str = Query("json", description="json or csv"),
):
    """Export all observations as JSON or CSV."""
    t0 = time.time()
    conn = get_observations_connection()
    try:
        rows = conn.execute("""
            SELECT data_point_ref, data_point_type, context_json, note, tags, created_at, updated_at
            FROM observations
            ORDER BY updated_at DESC
        """).fetchall()

        data = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/export/observations — %d rows, %.3fs", len(data), elapsed)

        if format == "csv":
            output = io.StringIO()
            if data:
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=observations.csv"},
            )

        return {"observations": data, "count": len(data)}
    finally:
        conn.close()
