# treehopper/logging.py
import logging
import json
import time
import os
from pathlib import Path
from typing import Any, Dict
from logging.handlers import RotatingFileHandler

from treehopper.th_config import (
    TH_ROOT,
    DEFAULT_BACKUP_COUNT,
    DEFAULT_LOG_NAME,
    DEFAULT_MAX_BYTES,
)

# -------------------------------------------------------------------
# JSON Structured Formatter
# -------------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: Dict[str, Any] = {
            "ts": int(time.time()),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        if hasattr(record, "extra") and isinstance(record.extra, dict):
            data.update(record.extra)

        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)

        return json.dumps(data, ensure_ascii=False)


# -------------------------------------------------------------------
# Rotating JSON Logger Factory
# -------------------------------------------------------------------


def get_logger(
    name: str = DEFAULT_LOG_NAME,
    level: int = logging.INFO,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> logging.Logger:

    logger = logging.getLogger(name)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Ensure log directory exists
    try:
        th_root = Path(os.getenv("TH_ROOT", TH_ROOT))
    except Exception:
        th_root = Path(TH_ROOT)

    log_dir = th_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Stable filename — NOT timestamped
    log_file = log_dir / f"{name}.log"
    latest_link = log_dir / f"{name}_latest.log"

    # Rotating handler
    try:
        handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

        # Maintain symlink
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()

        try:
            latest_link.symlink_to(log_file)
        except Exception:
            # Windows fallback
            import shutil

            shutil.copy(log_file, latest_link)

    except Exception as e:
        # Fallback to console if file logger fails
        console = logging.StreamHandler()
        console.setFormatter(JsonFormatter())
        logger.addHandler(console)
        logger.warning(
            "Failed to initialize rotating file logger", extra={"exception": str(e)}
        )

    return logger


# -------------------------------------------------------------------
# In-process Metrics
# -------------------------------------------------------------------


class Metrics:
    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}

    def incr(self, name: str, n: int = 1):
        self.counters[name] = self.counters.get(name, 0) + n

    def set_gauge(self, name: str, value: float):
        self.gauges[name] = value

    def snapshot(self) -> Dict[str, Any]:
        return {"counters": dict(self.counters), "gauges": dict(self.gauges)}


_metrics = Metrics()


def metrics() -> Metrics:
    return _metrics


def print_helper(message: str):
    logger = get_logger()
    print(message.strip())
    logger.info(message.strip())
    return None
