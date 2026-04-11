"""
Observation logging API.

CRUD for persistent notes on any data point in the system.
Uses atomic upsert via INSERT ... ON CONFLICT for idempotency (no race conditions).
Previous notes are archived in observation_history via trigger-like logic.
"""
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.core.connection import get_observations_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/observations", tags=["observations"])


class ObservationCreate(BaseModel):
    data_point_ref: str
    data_point_type: str
    context_json: dict
    note: str
    tags: Optional[str] = None


@router.post("")
def create_or_update_observation(body: ObservationCreate):
    """
    Create or update an observation. Atomic upsert on data_point_ref.
    If the observation already exists, archives the previous note in history
    then updates. Uses a transaction to prevent race conditions.
    """
    logger.info("POST /api/observations — ref=%s, type=%s...", body.data_point_ref, body.data_point_type)
    t0 = time.time()
    conn = get_observations_connection()
    try:
        # Use a transaction for atomicity
        with conn:
            existing = conn.execute(
                "SELECT observation_id, note FROM observations WHERE data_point_ref = ?",
                (body.data_point_ref,)
            ).fetchone()

            if existing:
                # Archive previous note before updating
                conn.execute(
                    "INSERT INTO observation_history (observation_id, previous_note) VALUES (?, ?)",
                    (existing["observation_id"], existing["note"])
                )
                conn.execute("""
                    UPDATE observations
                    SET note = ?, tags = ?, context_json = ?, updated_at = datetime('now')
                    WHERE data_point_ref = ?
                """, (body.note, body.tags, json.dumps(body.context_json), body.data_point_ref))
                status = "updated"
            else:
                conn.execute("""
                    INSERT INTO observations (data_point_ref, data_point_type, context_json, note, tags)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    body.data_point_ref,
                    body.data_point_type,
                    json.dumps(body.context_json),
                    body.note,
                    body.tags,
                ))
                status = "created"

        elapsed = time.time() - t0
        logger.info("POST /api/observations — %s %s, %.3fs", status, body.data_point_ref, elapsed)
        return {"status": status, "data_point_ref": body.data_point_ref}
    except Exception as e:
        logger.error("POST /api/observations — failed for ref=%s: %s", body.data_point_ref, e)
        raise
    finally:
        conn.close()


@router.get("")
def list_observations(
    data_point_type: Optional[str] = Query(None),
    tags: Optional[str] = Query(None, description="Comma-separated tag filter"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List observations with optional filters."""
    logger.info("GET /api/observations — type=%s, tags=%s, limit=%d, offset=%d...",
                data_point_type or "all", tags or "none", limit, offset)
    t0 = time.time()
    conn = get_observations_connection()
    try:
        sql = "SELECT * FROM observations WHERE 1=1"
        params: list = []
        if data_point_type:
            sql += " AND data_point_type = ?"
            params.append(data_point_type)
        if tags:
            for tag in tags.split(","):
                sql += " AND tags LIKE ?"
                params.append(f"%{tag.strip()}%")
        sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(sql, params).fetchall()
        result = [dict(r) for r in rows]
        elapsed = time.time() - t0
        logger.info("GET /api/observations — %d rows returned, %.3fs", len(result), elapsed)
        return {"observations": result, "count": len(result)}
    except Exception as e:
        logger.error("GET /api/observations — failed: %s", e)
        raise
    finally:
        conn.close()


@router.get("/{ref:path}")
def get_observation(ref: str):
    """Get a single observation by data_point_ref."""
    logger.info("GET /api/observations/%s...", ref)
    conn = get_observations_connection()
    try:
        row = conn.execute(
            "SELECT * FROM observations WHERE data_point_ref = ?", (ref,)
        ).fetchone()
        if not row:
            logger.info("GET /api/observations/%s — not found", ref)
            raise HTTPException(status_code=404, detail=f"No observation for {ref}")

        history = conn.execute(
            "SELECT previous_note, changed_at FROM observation_history WHERE observation_id = ? ORDER BY changed_at DESC",
            (row["observation_id"],)
        ).fetchall()

        logger.info("GET /api/observations/%s — found, %d history entries", ref, len(history))
        return {
            "observation": dict(row),
            "history": [dict(h) for h in history],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/observations/%s — failed: %s", ref, e)
        raise
    finally:
        conn.close()


@router.delete("/{ref:path}")
def delete_observation(ref: str):
    """Delete an observation by data_point_ref."""
    logger.info("DELETE /api/observations/%s...", ref)
    conn = get_observations_connection()
    try:
        row = conn.execute(
            "SELECT observation_id FROM observations WHERE data_point_ref = ?", (ref,)
        ).fetchone()
        if not row:
            logger.info("DELETE /api/observations/%s — not found", ref)
            raise HTTPException(status_code=404, detail=f"No observation for {ref}")

        with conn:
            conn.execute("DELETE FROM observation_history WHERE observation_id = ?", (row["observation_id"],))
            conn.execute("DELETE FROM observations WHERE observation_id = ?", (row["observation_id"],))

        logger.info("DELETE /api/observations/%s — deleted (id=%d)", ref, row["observation_id"])
        return {"status": "deleted", "data_point_ref": ref}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("DELETE /api/observations/%s — failed: %s", ref, e)
        raise
    finally:
        conn.close()
