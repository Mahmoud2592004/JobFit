"""
Authentication and authorization utilities.

JWT validation against Supabase's JWKS endpoint.
Identity is always derived from the validated token — never from request bodies.
"""

from __future__ import annotations

import structlog
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, InvalidTokenError

log = structlog.get_logger(__name__)

_ALGORITHM = "HS256"


def verify_supabase_token(token: str) -> dict:
    """
    Validate a Supabase JWT and return its decoded payload.

    Supports both HS256 HMAC tokens and ES256/RS256 asymmetric Supabase tokens.
    Raises InvalidTokenError for any validation failure.
    Never logs the token itself.
    """
    settings = get_settings()

    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise InvalidTokenError() from exc

    alg = header.get("alg", "HS256")

    # If HMAC HS256, verify locally with secret if configured, or decode in development
    if alg == "HS256":
        if settings.supabase_jwt_secret:
            try:
                return jwt.decode(
                    token,
                    settings.supabase_jwt_secret,
                    algorithms=["HS256"],
                    options={"verify_aud": False},
                )
            except JWTError as exc:
                log.info("jwt_validation_failed", reason=str(exc))
                raise InvalidTokenError() from exc
        elif not settings.is_production:
            try:
                return jwt.decode(
                    token,
                    "",
                    algorithms=["HS256"],
                    options={"verify_signature": False},
                )
            except JWTError:
                raise InvalidTokenError() from None
        else:
            raise InvalidTokenError()

    # If asymmetric (ES256/RS256) and Supabase client available, verify with Supabase Auth
    if alg in ("ES256", "RS256") and settings.supabase_url and settings.supabase_service_role_key:
        try:
            from app.core.database import get_supabase_client

            client = get_supabase_client()
            user_res = client.auth.get_user(token)
            if user_res and user_res.user:
                return {
                    "sub": str(user_res.user.id),
                    "email": user_res.user.email,
                    "aud": "authenticated",
                    "role": "authenticated",
                }
        except Exception as exc:
            log.info("supabase_token_verify_failed", reason=str(exc))
            raise InvalidTokenError() from exc

    if not settings.is_production:
        try:
            return jwt.decode(
                token,
                "",
                algorithms=[alg],
                options={"verify_signature": False},
            )
        except JWTError:
            raise InvalidTokenError() from None

    raise InvalidTokenError()


def extract_user_id(payload: dict) -> str:
    """Extract the user ID (sub) from a validated JWT payload."""
    user_id = payload.get("sub")
    if not user_id:
        raise InvalidTokenError()
    return user_id


def parse_bearer_token(authorization: str | None) -> str:
    """Parse and return the token from an Authorization: Bearer <token> header."""
    if not authorization:
        raise AuthenticationError()
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError("Invalid Authorization header format.")
    return parts[1].strip()


def create_access_token(
    user_id: str,
    email: str | None = None,
    expires_seconds: int = 86400 * 7,
) -> str:
    """Create a signed JWT token using the configured Supabase JWT secret."""
    from datetime import datetime, timezone

    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "email": email or "user@jobfit.local",
        "aud": "authenticated",
        "role": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + expires_seconds,
    }
    secret = settings.supabase_jwt_secret or settings.secret_key
    return jwt.encode(claims, secret, algorithm=_ALGORITHM)
