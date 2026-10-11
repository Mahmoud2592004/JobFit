"""
Job listings and search runs repository.
Handles deduplicated storage, caching queries, and discovery audit records.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import structlog

from app.core.exceptions import ProviderError
from app.repositories.base import BaseRepository
from app.schemas.job import CanonicalJob

log = structlog.get_logger(__name__)


class JobRepository(BaseRepository):
    """Data access repository for jobs and user search runs."""

    async def upsert_jobs(self, jobs: list[CanonicalJob]) -> list[dict[str, Any]]:
        """
        Bulk upsert canonical jobs on conflict (source_name, source_job_id).
        Refreshes retrieved_at timestamp and un-expires jobs.
        """
        if not jobs:
            return []

        records = [
            {
                "source_name": j.source_name,
                "source_job_id": j.source_job_id,
                "canonical_url": j.canonical_url,
                "title": j.title,
                "employer": j.employer,
                "location": j.location,
                "work_arrangement": j.work_arrangement,
                "employment_type": j.employment_type,
                "seniority": j.seniority,
                "description": j.description,
                "salary_min": j.salary_min,
                "salary_max": j.salary_max,
                "salary_currency": j.salary_currency,
                "published_at": j.published_at.isoformat() if j.published_at else None,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "is_expired": False,
                "attribution": j.attribution,
            }
            for j in jobs
        ]

        try:
            res = (
                self.client.table("jobs")
                .upsert(records, on_conflict="source_name,source_job_id")
                .execute()
            )
            return self.cast_records(res.data)
        except Exception as exc:
            log.error("jobs_upsert_failed", error=str(exc), count=len(records))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def get_job(self, job_id: UUID | str) -> dict[str, Any] | None:
        """Fetch a single job listing by primary key ID."""
        jid = self.ensure_uuid_str(job_id)
        try:
            res = self.client.table("jobs").select("*").eq("id", jid).limit(1).execute()
            records = self.cast_records(res.data)
            return records[0] if records else None
        except Exception as exc:
            log.error("get_job_failed", job_id=jid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def list_jobs(
        self,
        query: str | None = None,
        location: str | None = None,
        work_arrangement: str | None = None,
        employment_type: str | None = None,
        seniority: str | None = None,
        date_posted: str | None = None,
        remote_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List active jobs with text search and rich LinkedIn-compatible filters."""
        try:
            builder = (
                self.client.table("jobs")
                .select("*")
                .eq("is_expired", False)
                .order("retrieved_at", desc=True)
            )

            # 1. Work Arrangement Filter
            if work_arrangement and work_arrangement.lower() != "any":
                builder = builder.ilike("work_arrangement", f"%{work_arrangement.strip().lower()}%")
            elif remote_only:
                builder = builder.eq("work_arrangement", "remote")

            # 2. Location Filter
            if location and location.strip() and location.lower() not in {"any", "worldwide", "all"}:
                builder = builder.ilike("location", f"%{location.strip()}%")

            # 3. Employment Type Filter (e.g. Full-time, Part-time, Internship)
            if employment_type and employment_type.lower() != "any":
                builder = builder.ilike("employment_type", f"%{employment_type.strip().lower()}%")

            # 4. Seniority / Experience Level Filter (e.g. Internship, Entry, Mid, Senior)
            if seniority and seniority.lower() != "any":
                builder = builder.ilike("seniority", f"%{seniority.strip().lower()}%")

            # 5. Date Posted Freshness Filter
            if date_posted and date_posted != "anyTime":
                now = datetime.now(timezone.utc)
                if date_posted == "past24Hours":
                    cutoff = now - timedelta(hours=24)
                elif date_posted == "pastWeek":
                    cutoff = now - timedelta(days=7)
                elif date_posted == "pastMonth":
                    cutoff = now - timedelta(days=30)
                else:
                    cutoff = None

                if cutoff:
                    builder = builder.gte("retrieved_at", cutoff.isoformat())

            # 6. Keywords Query
            if query and query.strip():
                builder = builder.ilike("title", f"%{query.strip()}%")

            builder = builder.range(offset, offset + limit - 1)
            res = builder.execute()
            records = self.cast_records(res.data)

            # If restrictive filters return 0 records, fallback gracefully to broader keywords
            if not records and (location or work_arrangement or employment_type or seniority or date_posted):
                fallback_builder = (
                    self.client.table("jobs")
                    .select("*")
                    .eq("is_expired", False)
                    .order("retrieved_at", desc=True)
                )
                if query and query.strip():
                    fallback_builder = fallback_builder.ilike("title", f"%{query.strip()}%")
                fallback_builder = fallback_builder.range(offset, offset + limit - 1)
                fb_res = fallback_builder.execute()
                records = self.cast_records(fb_res.data)

            return records
        except Exception as exc:
            log.error("list_jobs_failed", query=query, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def create_search_run(
        self,
        user_id: UUID | str,
        profile_version_id: UUID | str | None,
        preferences_snapshot: dict[str, Any],
        providers_used: list[str],
    ) -> dict[str, Any]:
        """Record the start of a user job search run."""
        uid = self.ensure_uuid_str(user_id)
        pvid = self.ensure_uuid_str(profile_version_id) if profile_version_id else None

        record = {
            "user_id": uid,
            "profile_version_id": pvid,
            "preferences_snapshot": preferences_snapshot,
            "status": "running",
            "providers_used": providers_used,
            "jobs_found": 0,
            "matches_created": 0,
            "retry_count": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            res = self.client.table("search_runs").insert(record).execute()
            data = self.cast_records(res.data)
            return data[0] if data else {}
        except Exception as exc:
            log.error("create_search_run_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def update_search_run(
        self,
        run_id: UUID | str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update status, error summary, or metrics on a search run."""
        rid = self.ensure_uuid_str(run_id)
        try:
            res = self.client.table("search_runs").update(updates).eq("id", rid).execute()
            data = self.cast_records(res.data)
            return data[0] if data else {}
        except Exception as exc:
            log.error("update_search_run_failed", run_id=rid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def list_search_runs(
        self,
        user_id: UUID | str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List historical search runs for a user ordered newest first."""
        uid = self.ensure_uuid_str(user_id)
        try:
            res = (
                self.client.table("search_runs")
                .select("*")
                .eq("user_id", uid)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return self.cast_records(res.data)
        except Exception as exc:
            log.error("list_search_runs_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def delete_search_run(
        self,
        user_id: UUID | str,
        run_id: UUID | str,
    ) -> bool:
        """Delete a historical search run for a user."""
        uid = self.ensure_uuid_str(user_id)
        rid = self.ensure_uuid_str(run_id)
        try:
            self.client.table("search_runs").delete().eq("user_id", uid).eq("id", rid).execute()
            return True
        except Exception as exc:
            log.error("delete_search_run_failed", user_id=uid, run_id=rid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

