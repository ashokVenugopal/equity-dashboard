"""
Search API — company search by symbol, name, or ISIN.
Foundation for the Bloomberg-style command bar (Phase 4 adds filter parsing).
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, Query

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/companies")
def search_companies(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
):
    """Search companies by symbol, name, or ISIN. Fuzzy matching via LIKE."""
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        term = q.strip().upper()
        rows = conn.execute("""
            SELECT symbol, name, isin
            FROM companies
            WHERE symbol LIKE ? OR UPPER(name) LIKE ? OR isin LIKE ?
            ORDER BY
                CASE
                    WHEN symbol = ? THEN 1
                    WHEN symbol LIKE ? THEN 2
                    WHEN UPPER(name) LIKE ? THEN 3
                    ELSE 4
                END,
                symbol
            LIMIT ?
        """, (
            f"{term}%", f"%{term}%", f"{term}%",
            term, f"{term}%", f"%{term}%",
            limit,
        )).fetchall()

        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/search/companies?q=%s — %d results, %.3fs", q, len(result), elapsed)
        return {"query": q, "results": result, "count": len(result)}
    finally:
        conn.close()
