"""
Shared test fixtures for the equity-dashboard backend.

Creates in-memory SQLite databases with sample data for testing.
Follows project_guidelines.md: pytest fixtures, no network calls, fresh state per test.
"""
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
import yaml

from backend.core.config import reset_config_cache, set_config_path
from backend.core.connection import bootstrap_observations_schema


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for test artifacts."""
    return tmp_path


@pytest.fixture
def sample_pipeline_db(tmp_path):
    """
    Create an in-memory-like SQLite DB with the pipeline schema and sample data.
    Returns the path to the temporary database file.
    """
    db_path = tmp_path / "test_facts.sqlite3"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row

    # Bootstrap schema from equity-shared
    _bootstrap_schema(conn)

    # Seed sample data
    _seed_sample_data(conn)

    conn.commit()
    conn.close()
    return str(db_path)


@pytest.fixture
def sample_observations_db(tmp_path):
    """Create a temporary observations database."""
    db_path = tmp_path / "test_observations.sqlite3"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    bootstrap_observations_schema(conn)
    conn.close()
    return str(db_path)


@pytest.fixture
def test_config(tmp_path, sample_pipeline_db, sample_observations_db):
    """
    Create a test config.yaml pointing to the temporary databases.
    Sets up the config path so all backend modules use test DBs.
    """
    config = {
        "pipeline": {"db_path": sample_pipeline_db},
        "observations": {"db_path": sample_observations_db},
        "server": {
            "host": "127.0.0.1",
            "port": 8999,
            "cors_origins": ["http://localhost:3000"],
        },
    }
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    set_config_path(config_path)
    yield config_path
    reset_config_cache()


@pytest.fixture
def test_client(test_config):
    """Create a FastAPI test client with test configuration."""
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)


def _bootstrap_schema(conn):
    """Create minimal schema for testing (subset of equity-shared schema.sql)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            company_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol       TEXT NOT NULL UNIQUE,
            slug         TEXT NOT NULL,
            isin         TEXT NOT NULL,
            name         TEXT,
            fy_end_month INTEGER DEFAULT 3,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS concepts (
            concept_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            concept_code TEXT NOT NULL UNIQUE,
            concept_name TEXT NOT NULL,
            section      TEXT NOT NULL,
            unit         TEXT NOT NULL DEFAULT 'inr_cr',
            is_core      INTEGER NOT NULL DEFAULT 1,
            is_volatile  INTEGER NOT NULL DEFAULT 0,
            description  TEXT
        );

        CREATE TABLE IF NOT EXISTS sources (
            source_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id     INTEGER NOT NULL REFERENCES companies(company_id),
            file_path      TEXT,
            file_type      TEXT,
            document_type  TEXT,
            period_type    TEXT,
            derivation     TEXT,
            statement_type TEXT,
            sheet_name     TEXT,
            ingested_at    TEXT NOT NULL DEFAULT (datetime('now')),
            source_hash    TEXT,
            metadata_json  TEXT
        );

        CREATE TABLE IF NOT EXISTS facts (
            fact_id             INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id           INTEGER NOT NULL REFERENCES sources(source_id),
            company_id          INTEGER NOT NULL REFERENCES companies(company_id),
            concept_id          INTEGER NOT NULL REFERENCES concepts(concept_id),
            period_end_date     TEXT,
            fiscal_year         TEXT,
            period_label        TEXT,
            value               REAL,
            raw_value           TEXT,
            unit                TEXT NOT NULL DEFAULT 'inr_cr',
            original_unit       TEXT,
            is_derived          INTEGER NOT NULL DEFAULT 0,
            derivation_formula  TEXT,
            extraction_metadata TEXT,
            created_at          TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_facts_lookup ON facts(company_id, concept_id, period_end_date, unit);

        CREATE TABLE IF NOT EXISTS instruments (
            instrument_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument_type TEXT NOT NULL,
            symbol         TEXT NOT NULL,
            name           TEXT NOT NULL,
            exchange       TEXT,
            company_id     INTEGER REFERENCES companies(company_id),
            currency       TEXT DEFAULT 'INR',
            is_active      INTEGER NOT NULL DEFAULT 1,
            metadata_json  TEXT,
            created_at     TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (instrument_type, symbol, exchange)
        );

        CREATE TABLE IF NOT EXISTS classifications (
            classification_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument_id       INTEGER NOT NULL REFERENCES instruments(instrument_id),
            classification_type TEXT NOT NULL,
            classification_name TEXT NOT NULL,
            effective_from      TEXT,
            effective_to        TEXT,
            sort_order          INTEGER,
            metadata_json       TEXT,
            created_at          TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS price_history (
            price_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument_id  INTEGER NOT NULL REFERENCES instruments(instrument_id),
            trade_date     TEXT NOT NULL,
            open           REAL,
            high           REAL,
            low            REAL,
            close          REAL NOT NULL,
            adj_close      REAL,
            volume         INTEGER,
            delivery_qty   INTEGER,
            source         TEXT NOT NULL,
            exchange       TEXT,
            created_at     TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (instrument_id, trade_date, source)
        );
        CREATE INDEX IF NOT EXISTS idx_price_history_lookup ON price_history(instrument_id, trade_date);

        CREATE TABLE IF NOT EXISTS institutional_flows (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            flow_date       TEXT NOT NULL,
            participant_type TEXT NOT NULL,
            segment         TEXT NOT NULL,
            buy_value       REAL,
            sell_value      REAL,
            net_value       REAL,
            source          TEXT NOT NULL,
            period_type     TEXT NOT NULL DEFAULT 'daily',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (flow_date, participant_type, segment, period_type, source)
        );

        CREATE TABLE IF NOT EXISTS market_breadth (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date           TEXT NOT NULL,
            exchange             TEXT NOT NULL DEFAULT 'NSE',
            advances             INTEGER,
            declines             INTEGER,
            unchanged            INTEGER,
            advance_decline_ratio REAL,
            new_52w_highs        INTEGER,
            new_52w_lows         INTEGER,
            total_traded         INTEGER,
            avg_delivery_pct     REAL,
            source               TEXT NOT NULL DEFAULT 'derived',
            created_at           TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (trade_date, exchange, source)
        );

        CREATE TABLE IF NOT EXISTS derived_technicals (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument_id  INTEGER NOT NULL REFERENCES instruments(instrument_id),
            trade_date     TEXT NOT NULL,
            indicator_code TEXT NOT NULL,
            value          REAL NOT NULL,
            source         TEXT NOT NULL DEFAULT 'derived',
            created_at     TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (instrument_id, trade_date, indicator_code, source)
        );

        CREATE TABLE IF NOT EXISTS fo_participant_positioning (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date          TEXT NOT NULL,
            participant_type    TEXT NOT NULL,
            instrument_category TEXT NOT NULL,
            long_contracts      INTEGER,
            short_contracts     INTEGER,
            long_value          REAL,
            short_value         REAL,
            source              TEXT NOT NULL DEFAULT 'nse_website',
            created_at          TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (trade_date, participant_type, instrument_category, source)
        );

        CREATE TABLE IF NOT EXISTS options_chain_snapshot (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument_symbol TEXT NOT NULL,
            trade_date        TEXT NOT NULL,
            expiry_date       TEXT NOT NULL,
            strike_price      REAL NOT NULL,
            option_type       TEXT NOT NULL,
            open_interest     INTEGER,
            change_in_oi      INTEGER,
            volume            INTEGER,
            last_price        REAL,
            implied_volatility REAL,
            underlying_value  REAL,
            source            TEXT NOT NULL DEFAULT 'nse_website',
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (instrument_symbol, trade_date, expiry_date, strike_price, option_type, source)
        );

        CREATE TABLE IF NOT EXISTS fo_series_oi (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument_symbol TEXT NOT NULL,
            trade_date        TEXT NOT NULL,
            expiry_date       TEXT NOT NULL,
            futures_oi        INTEGER,
            futures_price     REAL,
            options_oi        INTEGER,
            total_oi          INTEGER,
            total_volume      INTEGER,
            source            TEXT NOT NULL DEFAULT 'nse_website',
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (instrument_symbol, trade_date, expiry_date, source)
        );

        -- best_fo_participant_positioning view
        CREATE VIEW IF NOT EXISTS best_fo_participant_positioning AS
        SELECT fp.*
        FROM fo_participant_positioning fp
        WHERE fp.id = (
            SELECT fp2.id FROM fo_participant_positioning fp2
            WHERE fp2.trade_date = fp.trade_date
              AND fp2.participant_type = fp.participant_type
              AND fp2.instrument_category = fp.instrument_category
            ORDER BY CASE fp2.source WHEN 'nse_website' THEN 1 WHEN 'manual' THEN 2 ELSE 3 END,
                     fp2.created_at DESC
            LIMIT 1
        );

        CREATE TABLE IF NOT EXISTS sector_performance (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            classification_type TEXT NOT NULL,
            classification_name TEXT NOT NULL,
            compute_date        TEXT NOT NULL,
            timeframe           TEXT NOT NULL,
            metric              TEXT NOT NULL,
            value               REAL NOT NULL,
            source              TEXT NOT NULL DEFAULT 'derived',
            created_at          TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (classification_type, classification_name, compute_date, timeframe, metric, source)
        );

        -- best_technicals view
        CREATE VIEW IF NOT EXISTS best_technicals AS
        SELECT dt.*, i.instrument_type, i.symbol, i.name AS instrument_name
        FROM derived_technicals dt
        JOIN instruments i ON dt.instrument_id = i.instrument_id
        WHERE dt.id = (
            SELECT dt2.id FROM derived_technicals dt2
            WHERE dt2.instrument_id = dt.instrument_id
              AND dt2.trade_date = dt.trade_date
              AND dt2.indicator_code = dt.indicator_code
            ORDER BY CASE dt2.source WHEN 'derived' THEN 1 WHEN 'external' THEN 2 ELSE 3 END,
                     dt2.created_at DESC
            LIMIT 1
        );

        -- Simplified best_prices view
        CREATE VIEW IF NOT EXISTS best_prices AS
        SELECT ph.*,
               i.instrument_type, i.symbol, i.name AS instrument_name, i.currency
        FROM price_history ph
        JOIN instruments i ON ph.instrument_id = i.instrument_id
        WHERE ph.price_id = (
            SELECT ph2.price_id
            FROM price_history ph2
            WHERE ph2.instrument_id = ph.instrument_id
              AND ph2.trade_date = ph.trade_date
            ORDER BY
                CASE ph2.source
                    WHEN 'nse_bhavcopy' THEN 1
                    WHEN 'bse_bhavcopy' THEN 2
                    WHEN 'nse_index' THEN 3
                    WHEN 'yahoo_finance' THEN 4
                    WHEN 'manual' THEN 5
                    ELSE 6
                END,
                ph2.created_at DESC
            LIMIT 1
        );

        -- Simplified best_institutional_flows view
        CREATE VIEW IF NOT EXISTS best_institutional_flows AS
        SELECT f.*
        FROM institutional_flows f
        WHERE f.id = (
            SELECT f2.id
            FROM institutional_flows f2
            WHERE f2.flow_date = f.flow_date
              AND f2.participant_type = f.participant_type
              AND f2.segment = f.segment
              AND f2.period_type = f.period_type
            ORDER BY
                CASE f2.source
                    WHEN 'nse_website' THEN 1
                    WHEN 'trendlyne' THEN 2
                    WHEN 'manual' THEN 3
                    ELSE 4
                END,
                f2.created_at DESC
            LIMIT 1
        );

        -- Simplified best_facts_consolidated view
        CREATE VIEW IF NOT EXISTS best_facts_consolidated AS
        SELECT f.*, c.concept_code, c.concept_name
        FROM facts f
        JOIN sources s ON f.source_id = s.source_id
        JOIN concepts c ON f.concept_id = c.concept_id
        WHERE s.statement_type = 'consolidated'
          AND f.fact_id = (
            SELECT f2.fact_id
            FROM facts f2
            JOIN sources s2 ON f2.source_id = s2.source_id
            WHERE f2.company_id = f.company_id
              AND f2.concept_id = f.concept_id
              AND f2.period_end_date = f.period_end_date
              AND s2.period_type = s.period_type
              AND s2.statement_type = 'consolidated'
            ORDER BY
                CASE s2.derivation
                    WHEN 'original' THEN 1
                    WHEN 'aggregated' THEN 2
                    WHEN 'calculated' THEN 3
                    ELSE 4
                END,
                CASE s2.file_type
                    WHEN 'screener_excel' THEN 1
                    WHEN 'screener_web' THEN 2
                    WHEN 'tijori_web' THEN 3
                    WHEN 'calculated' THEN 4
                    ELSE 5
                END,
                f2.created_at DESC
            LIMIT 1
          );
    """)


def _seed_sample_data(conn):
    """Insert sample companies, instruments, prices, flows, and breadth for testing."""
    # Companies
    conn.execute("INSERT INTO companies (symbol, slug, isin, name) VALUES ('RELIANCE', 'reliance', 'INE002A01018', 'Reliance Industries')")
    conn.execute("INSERT INTO companies (symbol, slug, isin, name) VALUES ('HDFCBANK', 'hdfc-bank', 'INE040A01034', 'HDFC Bank')")
    conn.execute("INSERT INTO companies (symbol, slug, isin, name) VALUES ('TCS', 'tcs', 'INE467B01029', 'Tata Consultancy Services')")

    # Concepts
    conn.execute("INSERT INTO concepts (concept_code, concept_name, section, unit) VALUES ('sales', 'Sales / Revenue', 'profit_loss', 'inr_cr')")
    conn.execute("INSERT INTO concepts (concept_code, concept_name, section, unit) VALUES ('net_profit', 'Net Profit', 'profit_loss', 'inr_cr')")
    conn.execute("INSERT INTO concepts (concept_code, concept_name, section, unit) VALUES ('market_cap', 'Market Capitalisation', 'meta', 'inr_cr')")

    # Instruments — indices
    conn.execute("""INSERT INTO instruments (instrument_type, symbol, name, exchange, currency)
                    VALUES ('index', 'NIFTY50', 'NIFTY 50', 'NSE', 'INR')""")
    conn.execute("""INSERT INTO instruments (instrument_type, symbol, name, exchange, currency)
                    VALUES ('index', 'BANKNIFTY', 'NIFTY Bank', 'NSE', 'INR')""")

    # Instruments — stocks
    conn.execute("""INSERT INTO instruments (instrument_type, symbol, name, exchange, company_id, currency)
                    VALUES ('stock', 'RELIANCE', 'Reliance Industries', 'NSE', 1, 'INR')""")
    conn.execute("""INSERT INTO instruments (instrument_type, symbol, name, exchange, company_id, currency)
                    VALUES ('stock', 'HDFCBANK', 'HDFC Bank', 'NSE', 2, 'INR')""")

    # Instruments — global
    conn.execute("""INSERT INTO instruments (instrument_type, symbol, name, currency)
                    VALUES ('commodity', 'BRENTUSD', 'Brent Crude Oil', 'USD')""")
    conn.execute("""INSERT INTO instruments (instrument_type, symbol, name, currency)
                    VALUES ('forex', 'USDINR', 'USD/INR', 'INR')""")

    # Classifications — simulate version tracking with multiple active rows per stock
    # (This is what happens in production: each reconstitution creates new rows)
    # RELIANCE: 3 active rows from 3 versions (instrument_id=3)
    conn.execute("""INSERT INTO classifications (instrument_id, classification_type, classification_name, sort_order, effective_from)
                    VALUES (3, 'index_constituent', 'NIFTY 50', 1, '2024-01-01')""")
    conn.execute("""INSERT INTO classifications (instrument_id, classification_type, classification_name, sort_order, effective_from)
                    VALUES (3, 'index_constituent', 'NIFTY 50', 1, '2025-01-01')""")
    conn.execute("""INSERT INTO classifications (instrument_id, classification_type, classification_name, sort_order, effective_from)
                    VALUES (3, 'index_constituent', 'NIFTY 50', 1, '2026-01-01')""")
    # HDFCBANK: 2 active rows (instrument_id=4)
    conn.execute("""INSERT INTO classifications (instrument_id, classification_type, classification_name, sort_order, effective_from)
                    VALUES (4, 'index_constituent', 'NIFTY 50', 2, '2025-01-01')""")
    conn.execute("""INSERT INTO classifications (instrument_id, classification_type, classification_name, sort_order, effective_from)
                    VALUES (4, 'index_constituent', 'NIFTY 50', 2, '2026-01-01')""")

    # Price history — NIFTY50 (instrument_id=1)
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source, exchange)
                    VALUES (1, '2026-04-09', 22100.0, 22350.0, 22050.0, 22300.0, 100000, 'nse_index', 'NSE')""")
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source, exchange)
                    VALUES (1, '2026-04-10', 22300.0, 22500.0, 22200.0, 22450.0, 120000, 'nse_index', 'NSE')""")

    # Price history — BANKNIFTY (instrument_id=2)
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source, exchange)
                    VALUES (2, '2026-04-09', 48000.0, 48500.0, 47800.0, 48200.0, 50000, 'nse_index', 'NSE')""")
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source, exchange)
                    VALUES (2, '2026-04-10', 48200.0, 48700.0, 48100.0, 48600.0, 55000, 'nse_index', 'NSE')""")

    # Price history — global instruments
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source)
                    VALUES (5, '2026-04-10', 72.50, 73.20, 72.10, 72.80, 0, 'yahoo_finance')""")
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source)
                    VALUES (6, '2026-04-10', 85.10, 85.30, 84.90, 85.20, 0, 'yahoo_finance')""")

    # Institutional flows
    conn.execute("""INSERT INTO institutional_flows (flow_date, participant_type, segment, buy_value, sell_value, net_value, source, period_type)
                    VALUES ('2026-04-10', 'FII', 'CASH', 5000.0, 6500.0, -1500.0, 'nse_website', 'daily')""")
    conn.execute("""INSERT INTO institutional_flows (flow_date, participant_type, segment, buy_value, sell_value, net_value, source, period_type)
                    VALUES ('2026-04-10', 'DII', 'CASH', 7000.0, 4500.0, 2500.0, 'nse_website', 'daily')""")
    conn.execute("""INSERT INTO institutional_flows (flow_date, participant_type, segment, buy_value, sell_value, net_value, source, period_type)
                    VALUES ('2026-04-09', 'FII', 'CASH', 4800.0, 5200.0, -400.0, 'nse_website', 'daily')""")

    # Market breadth
    conn.execute("""INSERT INTO market_breadth (trade_date, exchange, advances, declines, unchanged, advance_decline_ratio, new_52w_highs, new_52w_lows, total_traded, avg_delivery_pct, source)
                    VALUES ('2026-04-10', 'NSE', 1200, 800, 50, 1.5, 45, 12, 2050, 42.5, 'derived')""")
    conn.execute("""INSERT INTO market_breadth (trade_date, exchange, advances, declines, unchanged, advance_decline_ratio, new_52w_highs, new_52w_lows, total_traded, avg_delivery_pct, source)
                    VALUES ('2026-04-09', 'NSE', 900, 1100, 60, 0.82, 30, 25, 2060, 40.1, 'derived')""")

    # TCS instrument + NIFTY NEXT 50 classification (for heatmap tab)
    conn.execute("""INSERT INTO instruments (instrument_type, symbol, name, exchange, company_id, currency)
                    VALUES ('stock', 'TCS', 'Tata Consultancy Services', 'NSE', 3, 'INR')""")
    conn.execute("""INSERT INTO classifications (instrument_id, classification_type, classification_name, sort_order, effective_from)
                    VALUES (7, 'index_constituent', 'NIFTY NEXT 50', 1, '2026-01-01')""")
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source, exchange)
                    VALUES (7, '2026-04-09', 3700.0, 3750.0, 3680.0, 3720.0, 2000000, 'nse_bhavcopy', 'NSE')""")
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source, exchange)
                    VALUES (7, '2026-04-10', 3720.0, 3780.0, 3710.0, 3760.0, 2200000, 'nse_bhavcopy', 'NSE')""")

    # Sector classifications
    conn.execute("""INSERT INTO classifications (instrument_id, classification_type, classification_name, sort_order)
                    VALUES (3, 'sector', 'Oil & Gas', 1)""")
    conn.execute("""INSERT INTO classifications (instrument_id, classification_type, classification_name, sort_order)
                    VALUES (4, 'sector', 'Banking Services', 1)""")

    # Sector performance
    conn.execute("""INSERT INTO sector_performance (classification_type, classification_name, compute_date, timeframe, metric, value)
                    VALUES ('sector', 'Oil & Gas', '2026-04-10', '1w', 'avg_return_pct', 2.5)""")
    conn.execute("""INSERT INTO sector_performance (classification_type, classification_name, compute_date, timeframe, metric, value)
                    VALUES ('sector', 'Oil & Gas', '2026-04-10', '4w', 'avg_return_pct', 5.1)""")
    conn.execute("""INSERT INTO sector_performance (classification_type, classification_name, compute_date, timeframe, metric, value)
                    VALUES ('sector', 'Banking Services', '2026-04-10', '1w', 'avg_return_pct', -1.2)""")
    conn.execute("""INSERT INTO sector_performance (classification_type, classification_name, compute_date, timeframe, metric, value)
                    VALUES ('sector', 'Banking Services', '2026-04-10', '4w', 'avg_return_pct', 3.0)""")

    # Price history — stocks (for constituents)
    # RELIANCE: NSE + BSE prices for same dates (tests source priority: nse_bhavcopy > bse_bhavcopy)
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source, exchange)
                    VALUES (3, '2026-04-09', 1380.0, 1400.0, 1370.0, 1390.0, 5000000, 'nse_bhavcopy', 'NSE')""")
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source, exchange)
                    VALUES (3, '2026-04-09', 1381.0, 1401.0, 1371.0, 1391.0, 4500000, 'bse_bhavcopy', 'BSE')""")
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source, exchange)
                    VALUES (3, '2026-04-10', 1390.0, 1420.0, 1385.0, 1415.0, 6000000, 'nse_bhavcopy', 'NSE')""")
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source, exchange)
                    VALUES (3, '2026-04-10', 1392.0, 1422.0, 1387.0, 1417.0, 5500000, 'bse_bhavcopy', 'BSE')""")
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source, exchange)
                    VALUES (4, '2026-04-09', 1750.0, 1770.0, 1740.0, 1760.0, 3000000, 'nse_bhavcopy', 'NSE')""")
    conn.execute("""INSERT INTO price_history (instrument_id, trade_date, open, high, low, close, volume, source, exchange)
                    VALUES (4, '2026-04-10', 1760.0, 1780.0, 1745.0, 1750.0, 3500000, 'nse_bhavcopy', 'NSE')""")

    # Derived technicals for stocks
    conn.execute("""INSERT INTO derived_technicals (instrument_id, trade_date, indicator_code, value)
                    VALUES (3, '2026-04-10', 'dma_50', 1350.0)""")
    conn.execute("""INSERT INTO derived_technicals (instrument_id, trade_date, indicator_code, value)
                    VALUES (3, '2026-04-10', 'dma_200', 1280.0)""")
    conn.execute("""INSERT INTO derived_technicals (instrument_id, trade_date, indicator_code, value)
                    VALUES (3, '2026-04-10', 'rsi_14', 62.5)""")
    conn.execute("""INSERT INTO derived_technicals (instrument_id, trade_date, indicator_code, value)
                    VALUES (3, '2026-04-10', 'high_52w', 1520.0)""")
    conn.execute("""INSERT INTO derived_technicals (instrument_id, trade_date, indicator_code, value)
                    VALUES (3, '2026-04-10', 'low_52w', 1100.0)""")
    conn.execute("""INSERT INTO derived_technicals (instrument_id, trade_date, indicator_code, value)
                    VALUES (3, '2026-04-10', 'daily_change_pct', 1.80)""")
    conn.execute("""INSERT INTO derived_technicals (instrument_id, trade_date, indicator_code, value)
                    VALUES (4, '2026-04-10', 'daily_change_pct', -0.57)""")

    # F&O participant positioning
    conn.execute("""INSERT INTO fo_participant_positioning (trade_date, participant_type, instrument_category, long_contracts, short_contracts, long_value, short_value)
                    VALUES ('2026-04-10', 'FII', 'INDEX_FUTURES', 120000, 180000, 15000.0, 22500.0)""")
    conn.execute("""INSERT INTO fo_participant_positioning (trade_date, participant_type, instrument_category, long_contracts, short_contracts, long_value, short_value)
                    VALUES ('2026-04-10', 'FII', 'INDEX_OPTIONS', 500000, 450000, 62500.0, 56250.0)""")

    # Options chain snapshot (for PCR)
    conn.execute("""INSERT INTO options_chain_snapshot (instrument_symbol, trade_date, expiry_date, strike_price, option_type, open_interest, volume, last_price)
                    VALUES ('NIFTY', '2026-04-10', '2026-04-24', 22000.0, 'PE', 5000000, 100000, 150.0)""")
    conn.execute("""INSERT INTO options_chain_snapshot (instrument_symbol, trade_date, expiry_date, strike_price, option_type, open_interest, volume, last_price)
                    VALUES ('NIFTY', '2026-04-10', '2026-04-24', 22000.0, 'CE', 6000000, 120000, 200.0)""")
    conn.execute("""INSERT INTO options_chain_snapshot (instrument_symbol, trade_date, expiry_date, strike_price, option_type, open_interest, volume, last_price)
                    VALUES ('NIFTY', '2026-04-10', '2026-04-24', 22500.0, 'PE', 3000000, 80000, 300.0)""")
    conn.execute("""INSERT INTO options_chain_snapshot (instrument_symbol, trade_date, expiry_date, strike_price, option_type, open_interest, volume, last_price)
                    VALUES ('NIFTY', '2026-04-10', '2026-04-24', 22500.0, 'CE', 4000000, 90000, 100.0)""")

    # F&O series OI
    conn.execute("""INSERT INTO fo_series_oi (instrument_symbol, trade_date, expiry_date, futures_oi, options_oi, total_oi, total_volume)
                    VALUES ('NIFTY', '2026-04-10', '2026-04-24', 1500000, 25000000, 26500000, 5000000)""")

    # Sources + Facts for testing
    conn.execute("""INSERT INTO sources (company_id, file_type, period_type, derivation, statement_type)
                    VALUES (1, 'screener_excel', 'annual', 'original', 'consolidated')""")
    conn.execute("""INSERT INTO facts (source_id, company_id, concept_id, period_end_date, fiscal_year, value, unit)
                    VALUES (1, 1, 1, '2025-03-31', '2024-2025', 69709.44, 'inr_cr')""")
    conn.execute("""INSERT INTO facts (source_id, company_id, concept_id, period_end_date, fiscal_year, value, unit)
                    VALUES (1, 1, 2, '2025-03-31', '2024-2025', 17850.0, 'inr_cr')""")
