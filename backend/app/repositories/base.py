"""
Base repository pattern.

All repositories operate with explicit user_id filters to guarantee
that cross-user data access is impossible at the application layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

if TYPE_CHECKING:
    from supabase import Client

log = structlog.get_logger(__name__)


class BaseRepository:
    """Base class for data access repositories."""

    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            from app.core.database import get_supabase_client

            self._client = get_supabase_client()
        return self._client

    @staticmethod
    def ensure_uuid_str(val: UUID | str) -> str:
        """Normalize UUID or string to string format."""
        return str(val)

    @staticmethod
    def cast_records(data: Any) -> list[dict[str, Any]]:
        """Type-safe cast of Supabase query result list."""
        if isinstance(data, list):
            return data  # type: ignore[return-value]
        return []

    @staticmethod
    def cast_single(data: Any) -> dict[str, Any] | None:
        """Type-safe cast of Supabase single query result dictionary."""
        if isinstance(data, dict):
            return data  # type: ignore[return-value]
        return None
