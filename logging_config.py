from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from settings import Settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }:
                continue
            lowered = key.casefold()
            if any(marker in lowered for marker in ("password", "secret", "token", "authorization", "cookie")):
                payload[key] = "[REDACTED]"
            else:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class ErrorOnlyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR


def configure_logging(settings: Settings) -> None:
    logs_dir: Path = settings.resolved_logs_dir
    formatter = JsonFormatter()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)

    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        app_handler = RotatingFileHandler(
            logs_dir / "app.log",
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        app_handler.setFormatter(formatter)
        root.addHandler(app_handler)

        error_handler = RotatingFileHandler(
            logs_dir / "errors.log",
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        error_handler.setFormatter(formatter)
        error_handler.addFilter(ErrorOnlyFilter())
        root.addHandler(error_handler)
    except OSError as exc:
        root.warning("file_logging_disabled", extra={"error": str(exc), "logs_dir": str(logs_dir)})
