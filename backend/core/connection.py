"""
SQLite connection management.

Two connection pools:
  - Pipeline DB (read-only): facts.sqlite3 from equity-experiments-2
  - Observations DB (read-write): local observations.sqlite3
"""
import logging
import os
import sqlite3
from pathlib import Path

from .config import get_observations_db_path, get_pipeline_db_path

logger = logging.getLogger(__name__)

_OBSERVATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    observation_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    data_point_ref  TEXT NOT NULL UNIQUE,
    data_point_type TEXT NOT NULL,
    context_json    TEXT NOT NULL,
    note            TEXT NOT NULL,
    tags            TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_observations_type ON observations(data_point_type);
CREATE INDEX IF NOT EXISTS idx_observations_created ON observations(created_at);

CREATE TABLE IF NOT EXISTS observation_history (
    history_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id  INTEGER NOT NULL REFERENCES observations(observation_id),
    previous_note   TEXT NOT NULL,
    changed_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_obs_history_obs ON observation_history(observation_id);
"""


def get_pipeline_connection() -> sqlite3.Connection:
    """
    Open a read-only connection to the pipeline facts database.
    Uses SQLite URI mode to enforce read-only at the connection level.
    """
    path = get_pipeline_db_path()
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Pipeline database not found: {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    # WAL mode cannot be set on read-only connections; it must already be set by the writer.
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    logger.debug("Pipeline DB connection opened (read-only): %s", path)
    return conn


def get_observations_connection() -> sqlite3.Connection:
    """
    Open a read-write connection to the observations database.
    Creates the database and schema if they don't exist.
    """
    path = get_observations_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(_OBSERVATIONS_SCHEMA)
    logger.debug("Observations DB connection opened (read-write): %s", path)
    return conn


def bootstrap_observations_schema(conn: sqlite3.Connection) -> None:
    """Ensure the observations schema exists. Idempotent."""
    conn.executescript(_OBSERVATIONS_SCHEMA)
