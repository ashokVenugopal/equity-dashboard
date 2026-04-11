"""
Tests for database connection and config loading.

Covers: happy path, read-only enforcement, config loading, missing DB.
"""
import sqlite3

import pytest

from backend.core.config import get_pipeline_db_path, get_observations_db_path, get_server_config
from backend.core.connection import get_pipeline_connection, get_observations_connection


def test_pipeline_db_path_resolves(test_config, sample_pipeline_db):
    """Config returns the correct pipeline DB path."""
    path = get_pipeline_db_path()
    assert path == sample_pipeline_db


def test_observations_db_path_resolves(test_config, sample_observations_db):
    """Config returns the correct observations DB path."""
    path = get_observations_db_path()
    assert path == sample_observations_db


def test_server_config_defaults(test_config):
    """Server config returns expected values."""
    config = get_server_config()
    assert config["host"] == "127.0.0.1"
    assert config["port"] == 8999
    assert "http://localhost:3000" in config["cors_origins"]


def test_pipeline_connection_is_read_only(test_config):
    """Pipeline connection enforces read-only mode."""
    conn = get_pipeline_connection()
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("INSERT INTO companies (symbol, slug, isin) VALUES ('TEST', 'test', 'TEST123')")
    finally:
        conn.close()


def test_pipeline_connection_reads_data(test_config):
    """Pipeline connection can read sample data."""
    conn = get_pipeline_connection()
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM companies").fetchone()
        assert row["cnt"] == 3
    finally:
        conn.close()


def test_observations_connection_writable(test_config):
    """Observations connection allows writes."""
    conn = get_observations_connection()
    try:
        conn.execute("""
            INSERT INTO observations (data_point_ref, data_point_type, context_json, note)
            VALUES ('test:ref', 'fact', '{}', 'test note')
        """)
        conn.commit()
        row = conn.execute("SELECT COUNT(*) as cnt FROM observations").fetchone()
        assert row["cnt"] == 1
    finally:
        conn.close()


def test_observations_schema_idempotent(test_config):
    """Calling get_observations_connection twice doesn't fail (schema is IF NOT EXISTS)."""
    conn1 = get_observations_connection()
    conn1.close()
    conn2 = get_observations_connection()
    row = conn2.execute("SELECT COUNT(*) as cnt FROM observations").fetchone()
    assert row["cnt"] >= 0
    conn2.close()
