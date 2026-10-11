"""
Base protocol interface for external job aggregators.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.schemas.job import CanonicalJob


class JobProvider(Protocol):
    """Protocol defining interface for job board providers."""

    name: str

    async def fetch_jobs(
        self,
        query: str | None = None,
        limit: int = 50,
        preferences: dict[str, Any] | None = None,
    ) -> list[CanonicalJob]:
        """
        Fetch and normalize jobs from external source.

        Must handle transient network errors gracefully and return empty list on failure,
        logging appropriate diagnostics without crashing callers.
        """
        ...
