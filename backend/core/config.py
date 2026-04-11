"""
YAML config loader for the dashboard backend.
Mirrors the pattern from equity-chatbased-interface/store/connection.py.
"""
import logging
import os
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_CONFIG: Optional[dict] = None
_CONFIG_PATH: Optional[Path] = None


def _load_config() -> dict:
    global _CONFIG, _CONFIG_PATH
    if _CONFIG is not None:
        return _CONFIG
    config_path = _CONFIG_PATH or (Path(__file__).resolve().parent.parent / "config.yaml")
    if not config_path.exists():
        raise FileNotFoundError(
            f"config.yaml not found at {config_path}. "
            "Copy config-example.yaml to config.yaml and set pipeline.db_path."
        )
    with open(config_path) as f:
        _CONFIG = yaml.safe_load(f) or {}
    logger.info("Config loaded from %s", config_path)
    return _CONFIG


def set_config_path(path: Path) -> None:
    """Override the config file path — useful for tests."""
    global _CONFIG_PATH
    _CONFIG_PATH = path
    reset_config_cache()


def reset_config_cache() -> None:
    """Clear the cached config."""
    global _CONFIG
    _CONFIG = None


def get_pipeline_db_path() -> str:
    """Return the configured pipeline DB path (facts.sqlite3), resolved relative to config dir."""
    config = _load_config()
    raw = (config.get("pipeline") or {}).get("db_path")
    if not raw:
        raise ValueError("config.yaml must set pipeline.db_path")
    path = os.path.expanduser(raw)
    if not os.path.isabs(path):
        config_dir = (_CONFIG_PATH or Path(__file__).resolve().parent.parent / "config.yaml").parent
        path = str((config_dir / path).resolve())
    return path


def get_observations_db_path() -> str:
    """Return the configured observations DB path, resolved relative to config dir."""
    config = _load_config()
    raw = (config.get("observations") or {}).get("db_path", "data/observations.sqlite3")
    path = os.path.expanduser(raw)
    if not os.path.isabs(path):
        config_dir = (_CONFIG_PATH or Path(__file__).resolve().parent.parent / "config.yaml").parent
        path = str((config_dir / path).resolve())
    return path


def get_server_config() -> dict:
    """Return server configuration with defaults."""
    config = _load_config()
    server = config.get("server") or {}
    return {
        "host": server.get("host", "0.0.0.0"),
        "port": int(server.get("port", 8000)),
        "cors_origins": server.get("cors_origins", ["http://localhost:3000"]),
    }
