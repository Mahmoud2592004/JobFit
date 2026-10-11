"""Tests for AppError hierarchy and HTTP mappings."""

from __future__ import annotations

from app.core.exceptions import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    FileTooLargeError,
    InvalidStateTransitionError,
    InvalidTokenError,
    MalformedFileError,
    NotFoundError,
    RateLimitError,
    UnsupportedFileTypeError,
    ValidationError,
)


def test_exception_status_codes():
    """Verify that exception classes map to the intended HTTP status codes."""
    assert ValidationError.status_code == 400
    assert AuthenticationError.status_code == 401
    assert InvalidTokenError.status_code == 401
    assert AuthorizationError.status_code == 403
    assert NotFoundError.status_code == 404
    assert ConflictError.status_code == 409
    assert FileTooLargeError.status_code == 413
    assert UnsupportedFileTypeError.status_code == 422
    assert MalformedFileError.status_code == 422
    assert InvalidStateTransitionError.status_code == 422
    assert RateLimitError.status_code == 429
    assert AppError.status_code == 500


def test_file_too_large_error_message():
    err = FileTooLargeError(max_mb=10)
    assert "10 MB" in err.message
    assert err.code == "file_too_large"


def test_not_found_error_message():
    err = NotFoundError("Profile")
    assert "Profile not found" in err.message
    assert err.code == "not_found"
