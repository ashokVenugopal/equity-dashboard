"""
Flight recorder logging setup.

Follows project_guidelines.md: logs to both file and stderr,
with %(asctime)s [%(levelname)s] %(message)s format.
"""
import logging
import os
from pathlib import Path


def setup_logging(log_dir: str = "data/logs", log_file: str = "dashboard.log", level: int = logging.INFO) -> None:
    """Configure logging to both file and stderr."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    formatter = logging.Formatter(fmt)

    file_handler = logging.FileHandler(log_path / log_file)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers on re-init
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    logging.info("Logging initialized. Log file: %s", log_path / log_file)
