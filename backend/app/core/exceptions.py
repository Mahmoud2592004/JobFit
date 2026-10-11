"""
Domain exception hierarchy and HTTP mapping.

All business-logic errors raise an AppError subclass.
The exception handler in main.py converts them to consistent JSON responses.
Stack traces are never exposed in HTTP responses.
"""

from __future__ import annotations

from http import HTTPStatus


class AppError(Exception):
    """Base class for all application errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or HTTPStatus(self.status_code).phrase
        super().__init__(self.message)


# ── 400 Bad Request ───────────────────────────────────────────────────────────


class ValidationError(AppError):
    status_code = 400
    code = "validation_error"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"

    def __init__(self, max_mb: int) -> None:
        super().__init__(f"File exceeds the maximum allowed size of {max_mb} MB.")


class UnsupportedFileTypeError(AppError):
    status_code = 422
    code = "unsupported_file_type"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or "File type is not supported. Upload a PDF or DOCX.")


class MalformedFileError(AppError):
    status_code = 422
    code = "malformed_file"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or "The uploaded file could not be processed.")


class InvalidStateTransitionError(AppError):
    status_code = 422
    code = "invalid_state_transition"


# ── 401 Unauthorized ──────────────────────────────────────────────────────────


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_required"

    def __init__(self, message: str = "Authentication is required.") -> None:
        super().__init__(message)


class InvalidTokenError(AppError):
    status_code = 401
    code = "invalid_token"

    def __init__(self) -> None:
        super().__init__("The provided authentication token is invalid or expired.")


# ── 403 Forbidden ─────────────────────────────────────────────────────────────


class AuthorizationError(AppError):
    status_code = 403
    code = "forbidden"

    def __init__(
        self, message: str = "You do not have permission to access this resource."
    ) -> None:
        super().__init__(message)


# ── 404 Not Found ─────────────────────────────────────────────────────────────


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"

    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(f"{resource} not found or not accessible.")


# ── 409 Conflict ──────────────────────────────────────────────────────────────


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class DuplicateError(ConflictError):
    code = "duplicate_record"

    def __init__(self, resource: str = "Record") -> None:
        super().__init__(f"{resource} already exists.")


# ── 429 Too Many Requests ─────────────────────────────────────────────────────


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limit_exceeded"

    def __init__(self, provider: str = "provider") -> None:
        super().__init__(f"Rate limit reached for {provider}. Please try again later.")


# ── 503 Service Unavailable ───────────────────────────────────────────────────


class ProviderError(AppError):
    status_code = 503
    code = "provider_unavailable"

    def __init__(self, provider: str, detail: str | None = None) -> None:
        super().__init__(
            f"The {provider} service is temporarily unavailable." + (f" {detail}" if detail else "")
        )


class LLMError(AppError):
    status_code = 503
    code = "llm_unavailable"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            "The AI service is temporarily unavailable." + (f" {detail}" if detail else "")
        )


class StorageError(AppError):
    status_code = 503
    code = "storage_error"
