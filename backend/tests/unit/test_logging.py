"""Tests for structlog configuration and sensitive field redaction."""

from __future__ import annotations

from app.core.logging import _redact_sensitive_fields, configure_logging


def test_redact_sensitive_fields():
    """Verify that passwords, tokens, API keys, and raw resume texts are redacted."""
    event_dict = {
        "event": "user_login",
        "username": "candidate@example.com",
        "password": "supersecretpassword",
        "token": "jwt.secret.token",
        "gemini_api_key": "AIzaSyFakeKey",
        "resume_text": "Experienced software engineer...",
        "user_id": "usr_123",
    }

    sanitized = _redact_sensitive_fields(None, "info", event_dict)

    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["token"] == "[REDACTED]"
    assert sanitized["gemini_api_key"] == "[REDACTED]"
    assert sanitized["resume_text"] == "[REDACTED]"
    assert sanitized["username"] == "candidate@example.com"
    assert sanitized["user_id"] == "usr_123"


def test_configure_logging_development():
    configure_logging(level="DEBUG", environment="development")


def test_configure_logging_production():
    configure_logging(level="INFO", environment="production")
