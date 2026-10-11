"""
FastAPI dependency functions used across all routes.

These provide:
- Verified user identity from Supabase JWT
- Database client access
- Common pagination parameters
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError
from app.core.security import extract_user_id, verify_supabase_token

log = structlog.get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
    request: Request = None,  # type: ignore[assignment]
) -> str:
    """
    Validate the Supabase JWT and return the authenticated user_id.

    Supports both 'Authorization: Bearer <token>' header and HttpOnly session cookies.
    This dependency MUST be used on every protected endpoint.
    The user_id is extracted from the verified token — never from request body.

    Raises:
        AuthenticationError: if no token is provided or the header is malformed.
        InvalidTokenError: if the JWT is invalid, expired, or has wrong signature.
    """
    token = credentials.credentials if credentials else None
    if not token and request is not None:
        token = request.cookies.get("sb_access_token") or request.cookies.get("access_token")

    if not token:
        raise AuthenticationError()

    payload = verify_supabase_token(token)
    user_id = extract_user_id(payload)

    structlog.contextvars.bind_contextvars(user_id=user_id)
    return user_id


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
    request: Request = None,  # type: ignore[assignment]
) -> str | None:
    """Extract authenticated user_id if token or session cookie is provided, else return None."""
    token = credentials.credentials if credentials else None
    if not token and request is not None:
        token = request.cookies.get("sb_access_token") or request.cookies.get("access_token")

    if not token:
        return None
    try:
        payload = verify_supabase_token(token)
        user_id = extract_user_id(payload)
        structlog.contextvars.bind_contextvars(user_id=user_id)
        return user_id
    except Exception:
        return None


CurrentUser = Annotated[str, Depends(get_current_user)]


class PaginationParams:
    """Standard pagination parameters for list endpoints."""

    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
        page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    ) -> None:
        self.page = page if isinstance(page, int) else 1
        self.page_size = page_size if isinstance(page_size, int) else 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


Pagination = Annotated[PaginationParams, Depends(PaginationParams)]
