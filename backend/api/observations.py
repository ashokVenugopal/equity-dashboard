"""
Observation logging API.

CRUD for persistent notes on any data point in the system.
Uses upsert (INSERT ... ON CONFLICT DO UPDATE) for idempotency.
Previous notes are archived in observation_history.
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


class ObservationUpdate(BaseModel):
    note: str
    tags: Optional[str] = None


@router.post("")
def create_or_update_observation(body: ObservationCreate):
    """
    Create or update an observation. Upsert on data_point_ref.
    If the observation already exists, archives the previous note in history.
    """
    t0 = time.time()
    conn = get_observations_connection()
    try:
        existing = conn.execute(
            "SELECT observation_id, note FROM observations WHERE data_point_ref = ?",
            (body.data_point_ref,)
        ).fetchone()

        if existing:
            # Archive previous note
            conn.execute(
                "INSERT INTO observation_history (observation_id, previous_note) VALUES (?, ?)",
                (existing["observation_id"], existing["note"])
            )
            # Update
            conn.execute("""
                UPDATE observations
                SET note = ?, tags = ?, updated_at = datetime('now')
                WHERE data_point_ref = ?
            """, (body.note, body.tags, body.data_point_ref))
            conn.commit()
            elapsed = time.time() - t0
            logger.info("POST /api/observations — updated %s, %.3fs", body.data_point_ref, elapsed)
            return {"status": "updated", "data_point_ref": body.data_point_ref}
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
            conn.commit()
            elapsed = time.time() - t0
            logger.info("POST /api/observations — created %s, %.3fs", body.data_point_ref, elapsed)
            return {"status": "created", "data_point_ref": body.data_point_ref}
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
    t0 = time.time()
    conn = get_observations_connection()
    try:
        sql = "SELECT * FROM observations WHERE 1=1"
        params = []
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
        logger.info("GET /api/observations — %d rows, %.3fs", len(result), elapsed)
        return {"observations": result, "count": len(result)}
    finally:
        conn.close()


@router.get("/{ref:path}")
def get_observation(ref: str):
    """Get a single observation by data_point_ref."""
    conn = get_observations_connection()
    try:
        row = conn.execute(
            "SELECT * FROM observations WHERE data_point_ref = ?", (ref,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"No observation for {ref}")

        history = conn.execute(
            "SELECT previous_note, changed_at FROM observation_history WHERE observation_id = ? ORDER BY changed_at DESC",
            (row["observation_id"],)
        ).fetchall()

        return {
            "observation": dict(row),
            "history": [dict(h) for h in history],
        }
    finally:
        conn.close()


@router.delete("/{ref:path}")
def delete_observation(ref: str):
    """Delete an observation by data_point_ref."""
    conn = get_observations_connection()
    try:
        row = conn.execute(
            "SELECT observation_id FROM observations WHERE data_point_ref = ?", (ref,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"No observation for {ref}")

        conn.execute("DELETE FROM observation_history WHERE observation_id = ?", (row["observation_id"],))
        conn.execute("DELETE FROM observations WHERE observation_id = ?", (row["observation_id"],))
        conn.commit()
        logger.info("DELETE /api/observations/%s", ref)
        return {"status": "deleted", "data_point_ref": ref}
    finally:
        conn.close()
