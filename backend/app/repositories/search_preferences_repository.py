"""
Repository for candidate job search preferences.

All operations filter strictly by user_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog

from app.core.exceptions import ProviderError
from app.repositories.base import BaseRepository

log = structlog.get_logger(__name__)


class SearchPreferencesRepository(BaseRepository):
    """Repository handling candidate search preferences."""

    async def get_preferences(self, user_id: UUID | str) -> dict[str, Any] | None:
        """Fetch saved job search preferences for a user."""
        uid = self.ensure_uuid_str(user_id)
        try:
            res = (
                self.client.table("search_preferences")
                .select("*")
                .eq("user_id", uid)
                .maybe_single()
                .execute()
            )
            return self.cast_single(res.data) if res else None
        except Exception as exc:
            log.error("repo_get_preferences_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def upsert_preferences(self, user_id: UUID | str, data: dict[str, Any]) -> dict[str, Any]:
        """Save or update candidate job search preferences."""
        uid = self.ensure_uuid_str(user_id)
        payload = {
            **data,
            "user_id": uid,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            res = (
                self.client.table("search_preferences")
                .upsert(payload, on_conflict="user_id")
                .execute()
            )
            records = self.cast_records(res.data)
            if not records:
                raise ProviderError(
                    provider="Database", detail="Failed to save search preferences."
                )
            return records[0]
        except Exception as exc:
            log.error("repo_upsert_preferences_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc
