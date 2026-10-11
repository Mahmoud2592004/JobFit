"""
Database client management for Supabase PostgreSQL.

Provides server-side Supabase client initialized with the service role key.
Application code strictly enforces user boundaries (user_id filters)
on all data access operations.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import structlog

from app.core.config import get_settings
from app.core.exceptions import ProviderError

if TYPE_CHECKING:
    from supabase import Client

log = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Return a cached Supabase Client instance.

    Uses service_role_key for backend administrative access.
    Throws ProviderError if Supabase is not properly configured.
    """
    settings = get_settings()

    if not settings.supabase_url or not settings.supabase_service_role_key:
        log.warning("supabase_unconfigured", url_set=bool(settings.supabase_url))
        raise ProviderError(
            provider="Supabase",
            detail="Supabase URL and Service Role Key must be configured.",
        )

    from supabase import create_client

    try:
        client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        return client
    except Exception as exc:
        log.error("supabase_client_init_failed", error=str(exc))
        raise ProviderError(provider="Supabase", detail=str(exc)) from exc
