"""
Structured JSON logging configuration.
Use `get_logger(__name__)` in every module.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    _RESERVED = {"message", "asctime", "levelname", "name", "pathname", "lineno"}

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        extras: dict[str, Any] = {
            k: v
            for k, v in record.__dict__.items()
            if not k.startswith("_") and k not in logging.LogRecord.__dict__ and k not in self._RESERVED
        }
        payload: dict[str, Any] = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if extras:
            payload["extra"] = extras
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Call once at application startup."""
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
