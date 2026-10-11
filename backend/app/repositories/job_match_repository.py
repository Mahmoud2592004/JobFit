"""
Data access repository for candidate job matches and bookmarks.
Enforces strict user isolation across all read, write, and bookmark operations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog

from app.core.exceptions import ProviderError
from app.repositories.base import BaseRepository

log = structlog.get_logger(__name__)


class JobMatchRepository(BaseRepository):
    """Repository handling job match persistence, score querying, and saving."""

    async def upsert_match(
        self,
        user_id: UUID | str,
        job_id: UUID | str,
        scoring_version: str,
        overall_score: float,
        score_breakdown: dict[str, Any],
        matching_evidence: list[str],
        missing_requirements: list[str],
        uncertain_factors: list[str],
        freshness_warning: str | None = None,
        search_run_id: UUID | str | None = None,
        profile_version_id: UUID | str | None = None,
    ) -> dict[str, Any]:
        """
        Upsert a job match evaluation for a candidate.
        Unique per (user_id, job_id, scoring_version).
        """
        uid = self.ensure_uuid_str(user_id)
        jid = self.ensure_uuid_str(job_id)
        srid = self.ensure_uuid_str(search_run_id) if search_run_id else None
        pvid = self.ensure_uuid_str(profile_version_id) if profile_version_id else None

        record = {
            "user_id": uid,
            "job_id": jid,
            "scoring_version": scoring_version,
            "overall_score": round(overall_score, 2),
            "score_breakdown": score_breakdown,
            "matching_evidence": matching_evidence,
            "missing_requirements": missing_requirements,
            "uncertain_factors": uncertain_factors,
            "freshness_warning": freshness_warning,
            "search_run_id": srid,
            "profile_version_id": pvid,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            res = (
                self.client.table("job_matches")
                .upsert(record, on_conflict="user_id,job_id,scoring_version")
                .execute()
            )
            records = self.cast_records(res.data)
            return records[0] if records else record
        except Exception as exc:
            log.error("upsert_match_failed", user_id=uid, job_id=jid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def get_match(
        self,
        user_id: UUID | str,
        match_id: UUID | str,
    ) -> dict[str, Any] | None:
        """Fetch single match record ensuring user ownership."""
        uid = self.ensure_uuid_str(user_id)
        mid = self.ensure_uuid_str(match_id)

        try:
            res = (
                self.client.table("job_matches")
                .select("*, job:jobs(*)")
                .eq("id", mid)
                .eq("user_id", uid)
                .limit(1)
                .execute()
            )
            records = self.cast_records(res.data)
            return records[0] if records else None
        except Exception as exc:
            log.error("get_match_failed", user_id=uid, match_id=mid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def get_match_by_job(
        self,
        user_id: UUID | str,
        job_id: UUID | str,
        scoring_version: str = "v1.0.0",
    ) -> dict[str, Any] | None:
        """Retrieve existing match evaluation for a specific job."""
        uid = self.ensure_uuid_str(user_id)
        jid = self.ensure_uuid_str(job_id)

        try:
            res = (
                self.client.table("job_matches")
                .select("*, job:jobs(*)")
                .eq("user_id", uid)
                .eq("job_id", jid)
                .eq("scoring_version", scoring_version)
                .limit(1)
                .execute()
            )
            records = self.cast_records(res.data)
            return records[0] if records else None
        except Exception as exc:
            log.error("get_match_by_job_failed", user_id=uid, job_id=jid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def list_matches(
        self,
        user_id: UUID | str,
        min_score: float | None = None,
        is_saved: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List user's matches ordered by overall_score descending."""
        uid = self.ensure_uuid_str(user_id)

        try:
            builder = (
                self.client.table("job_matches")
                .select("*, job:jobs(*)")
                .eq("user_id", uid)
                .order("overall_score", desc=True)
            )

            if min_score is not None:
                builder = builder.gte("overall_score", min_score)

            if is_saved is not None:
                builder = builder.eq("is_saved", is_saved)

            builder = builder.range(offset, offset + limit - 1)
            res = builder.execute()
            return self.cast_records(res.data)
        except Exception as exc:
            log.error("list_matches_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def set_saved_status(
        self,
        user_id: UUID | str,
        match_id: UUID | str,
        is_saved: bool,
    ) -> dict[str, Any] | None:
        """Update bookmark saved state on a user match."""
        uid = self.ensure_uuid_str(user_id)
        mid = self.ensure_uuid_str(match_id)

        saved_at = datetime.now(timezone.utc).isoformat() if is_saved else None
        updates = {"is_saved": is_saved, "saved_at": saved_at}

        try:
            res = (
                self.client.table("job_matches")
                .update(updates)
                .eq("id", mid)
                .eq("user_id", uid)
                .execute()
            )
            records = self.cast_records(res.data)
            return records[0] if records else None
        except Exception as exc:
            log.error("set_saved_status_failed", user_id=uid, match_id=mid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc
