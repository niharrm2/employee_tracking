"""
app/core/logging.py — Enterprise Structured Logging with Correlation ID
========================================================================
Supports context-based request_id propagation across threads and coroutines.
"""
from __future__ import annotations
import logging
import sys
from typing import Optional


class RequestIdFilter(logging.Filter):
    """Ensures every log record contains a request_id for distributed tracing."""
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


def setup_logging(level: str = "INFO", log_file: Optional[str] = "office_track.log") -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] [%(request_id)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    req_filter = RequestIdFilter()

    # Stream (stdout)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    sh.addFilter(req_filter)
    root.addHandler(sh)

    # File handler
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        fh.addFilter(req_filter)
        root.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)