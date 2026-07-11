"""
User preferences API — small key/value store in the observations DB for
UI settings that should persist across browsers and devices (e.g. the
volume-profiler placement). Not for data; values are short strings.
"""
import logging
import re

from fastapi import APIRouter, Body, HTTPException

from backend.core.connection import get_observations_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prefs", tags=["prefs"])

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_preferences (
    pref_key   TEXT PRIMARY KEY,
    pref_value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_KEY_RE = re.compile(r"^[\w.:-]{1,64}$")


def _conn():
    conn = get_observations_connection()
    conn.executescript(_SCHEMA)
    return conn


@router.get("/{key}")
def get_pref(key: str):
    if not _KEY_RE.match(key):
        raise HTTPException(status_code=400, detail="Invalid key")
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT pref_value FROM user_preferences WHERE pref_key = ?",
            (key,)).fetchone()
        return {"key": key, "value": row["pref_value"] if row else None}
    finally:
        conn.close()


@router.put("/{key}")
def set_pref(key: str, payload: dict = Body(...)):
    if not _KEY_RE.match(key):
        raise HTTPException(status_code=400, detail="Invalid key")
    value = payload.get("value")
    if not isinstance(value, str) or not value or len(value) > 512:
        raise HTTPException(status_code=400,
                            detail="value must be a non-empty string (<= 512 chars)")
    conn = _conn()
    try:
        with conn:
            conn.execute(
                "INSERT INTO user_preferences (pref_key, pref_value) VALUES (?, ?) "
                "ON CONFLICT(pref_key) DO UPDATE SET pref_value = excluded.pref_value, "
                "updated_at = datetime('now')", (key, value))
        logger.info("PUT /api/prefs/%s = %s", key, value)
        return {"key": key, "value": value}
    finally:
        conn.close()
