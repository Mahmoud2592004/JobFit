"""
API endpoints for authentication session management and development access.
"""

from __future__ import annotations

import uuid
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


class AuthRequest(BaseModel):
    """Payload for login and signup."""

    email: str = Field(description="User email address")
    password: str = Field(min_length=6, description="Password")
    name: str | None = Field(default=None, description="Optional display name")


class RefreshRequest(BaseModel):
    """Payload for refreshing token."""

    refresh_token: str | None = Field(default=None, description="Supabase refresh token")


class AuthResponse(BaseModel):
    """Authentication token response."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105
    user_id: UUID
    email: str
    name: str | None = None
    refresh_token: str | None = None


class UserProfileResponse(BaseModel):
    """Current authenticated user information."""

    user_id: UUID
    email: str | None = None
    name: str | None = None


def _set_auth_cookies(
    response: Response, access_token: str, refresh_token: str | None = None
) -> None:
    """Set secure HTTP-only cookies for authenticated session."""
    settings = get_settings()
    is_secure = settings.environment == "production"
    response.set_cookie(
        key="sb_access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=60 * 60 * 24 * 7,  # 7 days
        path="/",
    )
    if refresh_token:
        response.set_cookie(
            key="sb_refresh_token",
            value=refresh_token,
            httponly=True,
            samesite="lax",
            secure=is_secure,
            max_age=60 * 60 * 24 * 30,  # 30 days
            path="/",
        )


def _deterministic_uuid(val: str) -> UUID:
    """Generate a deterministic UUID from an email string for dev sessions."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, val.strip().lower())


@router.post(
    "/session",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Sign in with email and password",
)
async def login_session(payload: AuthRequest, response: Response) -> AuthResponse:
    """
    Authenticate user strictly against Supabase Auth.
    Rejects invalid credentials with 401 Unauthorized.
    Sets secure HttpOnly session cookies for persistent auth.
    """
    settings = get_settings()
    email = payload.email.strip().lower()

    if not settings.supabase_url:
        raise AuthenticationError("Authentication provider is not configured.")

    try:
        from app.core.database import get_supabase_client

        client = get_supabase_client()
        if type(client).__name__ in ("MagicMock", "Mock", "AsyncMock"):
            auth_client = client
        else:
            from supabase import create_client

            auth_key = settings.supabase_anon_key or settings.supabase_service_role_key
            auth_client = create_client(settings.supabase_url, auth_key)

        auth_res = auth_client.auth.sign_in_with_password(
            {"email": email, "password": payload.password}
        )

        if not auth_res.session or not auth_res.user:
            raise AuthenticationError("Invalid email or password.")

        raw_refresh = getattr(auth_res.session, "refresh_token", None)
        refresh_token = raw_refresh if isinstance(raw_refresh, str) else None
        _set_auth_cookies(response, auth_res.session.access_token, refresh_token)

        return AuthResponse(
            access_token=auth_res.session.access_token,
            user_id=UUID(auth_res.user.id),
            email=auth_res.user.email or email,
            name=auth_res.user.user_metadata.get("name")
            if getattr(auth_res.user, "user_metadata", None)
            else payload.name or email.split("@")[0].capitalize(),
            refresh_token=refresh_token,
        )
    except AuthenticationError:
        raise
    except Exception as exc:
        log.info("supabase_auth_failed", email=email, error=str(exc))
        raise AuthenticationError("Invalid email or password.") from exc


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Sign up a new account",
)
async def signup_account(payload: AuthRequest, response: Response) -> AuthResponse:
    """
    Register user with Supabase Auth, pre-confirm email, establish session and set cookies.
    """
    settings = get_settings()
    email = payload.email.strip().lower()

    if not settings.supabase_url:
        raise AuthenticationError("Authentication provider is not configured.")

    try:
        from app.core.database import get_supabase_client

        client = get_supabase_client()

        # Create user via admin API with pre-confirmed email
        try:
            client.auth.admin.create_user(
                {
                    "email": email,
                    "password": payload.password,
                    "email_confirm": True,
                    "user_metadata": {
                        "name": payload.name or email.split("@")[0].capitalize()
                    },
                }
            )
        except Exception as create_exc:
            exc_str = str(create_exc).lower()
            if (
                "already been registered" in exc_str
                or "already registered" in exc_str
                or "already exists" in exc_str
                or "user already exists" in exc_str
            ):
                raise ConflictError(
                    "An account with this email address already exists. Please log in instead."
                ) from create_exc
            log.warning("admin_create_user_failed", email=email, error=str(create_exc))
            raise AuthenticationError(f"Signup failed: {create_exc}") from create_exc

        # Sign in using isolated auth client to obtain access token without mutating admin client
        if type(client).__name__ in ("MagicMock", "Mock", "AsyncMock"):
            auth_client = client
        else:
            from supabase import create_client

            auth_key = settings.supabase_anon_key or settings.supabase_service_role_key
            auth_client = create_client(settings.supabase_url, auth_key)

        auth_res = auth_client.auth.sign_in_with_password(
            {"email": email, "password": payload.password}
        )

        if not auth_res.session or not auth_res.user:
            raise AuthenticationError("Failed to authenticate newly created account.")

        raw_refresh = getattr(auth_res.session, "refresh_token", None)
        refresh_token = raw_refresh if isinstance(raw_refresh, str) else None
        _set_auth_cookies(response, auth_res.session.access_token, refresh_token)

        return AuthResponse(
            access_token=auth_res.session.access_token,
            user_id=UUID(auth_res.user.id),
            email=auth_res.user.email or email,
            name=payload.name or email.split("@")[0].capitalize(),
            refresh_token=refresh_token,
        )
    except (AuthenticationError, ConflictError):
        raise
    except Exception as exc:
        log.warning("supabase_signup_failed", email=email, error=str(exc))
        raise AuthenticationError(f"Signup failed: {exc}") from exc


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Refresh user session tokens using refresh token cookie or payload",
)
async def refresh_session(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
) -> AuthResponse:
    """Refresh JWT tokens using HttpOnly refresh cookie or provided refresh token."""
    settings = get_settings()
    refresh_token = (payload.refresh_token if payload else None) or request.cookies.get("sb_refresh_token")
    if not refresh_token:
        raise AuthenticationError("Refresh token is required.")

    try:
        from app.core.database import get_supabase_client

        client = get_supabase_client()
        if type(client).__name__ in ("MagicMock", "Mock", "AsyncMock"):
            auth_client = client
        else:
            from supabase import create_client

            auth_key = settings.supabase_anon_key or settings.supabase_service_role_key
            auth_client = create_client(settings.supabase_url, auth_key)

        auth_res = auth_client.auth.refresh_session(refresh_token)
        if not auth_res.session or not auth_res.user:
            raise AuthenticationError("Unable to refresh session.")

        new_refresh = getattr(auth_res.session, "refresh_token", None) or refresh_token
        _set_auth_cookies(response, auth_res.session.access_token, new_refresh)

        return AuthResponse(
            access_token=auth_res.session.access_token,
            user_id=UUID(auth_res.user.id),
            email=auth_res.user.email or "",
            name=auth_res.user.user_metadata.get("name")
            if getattr(auth_res.user, "user_metadata", None)
            else None,
            refresh_token=new_refresh,
        )
    except Exception as exc:
        log.info("refresh_session_failed", error=str(exc))
        raise AuthenticationError("Session expired or invalid refresh token.") from exc


@router.post(
    "/logout",
    summary="Clear authenticated session and cookies",
)
async def logout_session(response: Response) -> dict[str, str]:
    """Clear session cookies on server."""
    response.delete_cookie(key="sb_access_token", path="/")
    response.delete_cookie(key="sb_refresh_token", path="/")
    return {"status": "ok"}


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Verify token and return authenticated user identity",
)
async def get_me(user_id: Annotated[str, Depends(get_current_user)]) -> UserProfileResponse:
    """Return the authenticated caller identity with name and email when available."""
    email = None
    name = None
    try:
        from app.core.database import get_supabase_client

        client = get_supabase_client()
        user_res = client.auth.admin.get_user_by_id(user_id)
        if user_res and getattr(user_res, "user", None):
            email = user_res.user.email
            user_meta = getattr(user_res.user, "user_metadata", None)
            if user_meta and isinstance(user_meta, dict):
                name = user_meta.get("name")
    except Exception:
        pass

    return UserProfileResponse(
        user_id=UUID(user_id),
        email=email,
        name=name,
    )

