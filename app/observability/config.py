import json
from datetime import UTC, datetime
from typing import Any

import structlog
from structlog.typing import EventDict, WrappedLogger


class LogRenderer:
    """Render one-line application logs for humans and GCP text search."""

    def __call__(
        self,
        logger: WrappedLogger,
        method_name: str,
        event_dict: EventDict,
    ) -> str:
        del logger, method_name
        level = str(event_dict.pop("level", "info")).upper()
        timestamp = event_dict.pop("timestamp", datetime.now(UTC).isoformat())
        message = event_dict.pop("event", "")
        details = " ".join(
            f"{key}={_format_value(value)}" for key, value in sorted(event_dict.items())
        )
        suffix = f" {details}" if details else ""
        return f"{level} - {timestamp}: {message}{suffix}"


def _format_value(value: Any) -> str:
    if isinstance(value, str) and not any(character.isspace() for character in value):
        return value
    return json.dumps(value, default=str, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> None:
    """Configure structured logging whose awaited methods run off-loop."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            LogRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
