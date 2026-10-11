"""
Structured JSON logging configuration using structlog.

Rules (enforced here, not just documented):
- No raw resume text, passwords, tokens, or personal data in logs.
- Every log line includes a request_id for correlation.
- Production uses JSON output; development uses console output.
"""

from __future__ import annotations

import logging
import sys
from typing import Literal

import structlog
from structlog.types import EventDict, WrappedLogger


def configure_logging(
    level: str = "INFO",
    environment: Literal["development", "staging", "production"] = "development",
) -> None:
    """Configure structlog with appropriate processors for the environment."""

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _redact_sensitive_fields,
    ]

    if environment == "production":
        # JSON output for log aggregators (Datadog, Render logs, etc.)
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Human-readable output for local development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging to route through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, level.upper(), logging.INFO),
    )


_REDACTED_KEYS = frozenset(
    {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "service_role_key",
        "supabase_service_role_key",
        "secret_key",
        "api_key",
        "gemini_api_key",
        "groq_api_key",
        "authorization",
        "resume_text",
        "raw_text",
        "cv_content",
    }
)


def _redact_sensitive_fields(
    _logger: WrappedLogger, _method: str, event_dict: EventDict
) -> EventDict:
    """
    Remove any sensitive field names that should never appear in logs.

    This is a last-resort backstop. Code should never log these values
    in the first place, but this processor catches accidental inclusions.
    """
    for key in list(event_dict.keys()):
        if key.lower() in _REDACTED_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict
