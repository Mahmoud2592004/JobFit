"""
Job Discovery Engine.
Orchestrates multi-provider fetching, deduplication, caching, and search run auditing.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog

from app.providers.jobs.base import JobProvider
from app.repositories.job_repository import JobRepository
from app.schemas.job import CanonicalJob

log = structlog.get_logger(__name__)


def _dedup_key(job: CanonicalJob) -> str:
    """Normalize employer and title into a deduplication fingerprint."""
    clean_employer = re.sub(r"[^a-z0-9]", "", job.employer.lower())
    clean_title = re.sub(r"[^a-z0-9]", "", job.title.lower())
    return f"{clean_employer}::{clean_title}"


class JobDiscoveryService:
    """Service orchestrating multi-source discovery, deduplication, and persistence."""

    def __init__(
        self,
        job_repo: JobRepository,
        providers: list[JobProvider] | None = None,
        preferences_repo: Any = None,
    ) -> None:
        self.job_repo = job_repo
        if preferences_repo is None:
            from app.repositories.search_preferences_repository import SearchPreferencesRepository

            self.preferences_repo = SearchPreferencesRepository()
        else:
            self.preferences_repo = preferences_repo

        if providers is None:
            from app.providers.jobs.linkedin_apify import LinkedInApifyProvider

            self.providers: list[JobProvider] = [LinkedInApifyProvider()]
        else:
            self.providers = providers

    async def discover_jobs(
        self,
        user_id: UUID | str,
        query: str,
        remote_only: bool = True,
        limit_per_provider: int = 10,
        profile_version_id: UUID | str | None = None,
        preferences: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute an on-demand multi-provider search, deduplicate results, and persist to database.
        Optimizes scraper input using candidate preferences.
        """
        active_prefs = dict(preferences or {})
        if not active_prefs and self.preferences_repo:
            try:
                db_prefs = await self.preferences_repo.get_preferences(user_id)
                if db_prefs:
                    active_prefs = dict(db_prefs)
            except Exception as exc:
                log.debug("could_not_fetch_user_preferences_for_discovery", error=str(exc))

        provider_names = [p.name for p in self.providers]
        preferences_snapshot = {
            "query": query,
            "remote_only": remote_only,
            "limit_per_provider": limit_per_provider,
            **{
                k: v
                for k, v in active_prefs.items()
                if k not in {"id", "user_id", "created_at", "updated_at"}
            },
        }

        # 1. Create audit record for the search run if valid user
        run_id = None
        if str(user_id) != "00000000-0000-0000-0000-000000000000":
            try:
                search_run = await self.job_repo.create_search_run(
                    user_id=user_id,
                    profile_version_id=profile_version_id,
                    preferences_snapshot=preferences_snapshot,
                    providers_used=provider_names,
                )
                if search_run:
                    run_id = search_run.get("id")
            except Exception as exc:
                log.warning("could_not_create_search_run_audit", error=str(exc))

        try:
            # 2. Extract target locations for fair geographic distribution across selected countries
            raw_locs = active_prefs.get("locations") or []
            if isinstance(raw_locs, str):
                target_locations = [l.strip() for l in raw_locs.split(",") if l.strip()]
            elif isinstance(raw_locs, list):
                target_locations = [str(l).strip() for l in raw_locs if str(l).strip()]
            else:
                target_locations = []

            if not target_locations and active_prefs.get("location"):
                target_locations = [l.strip() for l in str(active_prefs["location"]).split(",") if l.strip()]

            target_locations = [
                l for l in target_locations if l.lower() not in {"any", "worldwide", "all"}
            ]

            # If user selected multiple countries, divide limit evenly across countries
            tasks = []
            if len(target_locations) > 1:
                # Remove single country locking so Apify doesn't restrict all countries to one country code
                active_prefs.pop("split_country", None)
                active_prefs.pop("splitCountry", None)
                num_locs = len(target_locations)
                per_loc_limit = max(1, limit_per_provider // num_locs)
                remainder = limit_per_provider % num_locs

                for provider in self.providers:
                    for idx, loc in enumerate(target_locations):
                        loc_limit = per_loc_limit + (1 if idx < remainder else 0)
                        loc_prefs = {**active_prefs, "location": loc, "locations": [loc]}
                        tasks.append(
                            provider.fetch_jobs(
                                query=query,
                                limit=loc_limit,
                                preferences=loc_prefs,
                            )
                        )
            else:
                tasks = [
                    provider.fetch_jobs(
                        query=query,
                        limit=limit_per_provider,
                        preferences=active_prefs,
                    )
                    for provider in self.providers
                ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_jobs: list[CanonicalJob] = []
            for res in results:
                if isinstance(res, Exception):
                    log.error("provider_execution_error", error=str(res))
                elif isinstance(res, list):
                    all_jobs.extend(res)

            # 3. Deduplicate across providers
            seen_keys: set[str] = set()
            deduped_jobs: list[CanonicalJob] = []

            for job in all_jobs:
                if remote_only and job.work_arrangement == "onsite":
                    continue
                if remote_only and not job.work_arrangement:
                    job.work_arrangement = "remote"

                key = _dedup_key(job)
                if key not in seen_keys:
                    seen_keys.add(key)
                    deduped_jobs.append(job)

            # 4. Upsert discovered jobs into the repository
            saved_jobs = await self.job_repo.upsert_jobs(deduped_jobs)

            # 5. Complete search run audit record
            if run_id:
                await self.job_repo.update_search_run(
                    run_id=run_id,
                    updates={
                        "status": "completed",
                        "jobs_found": len(saved_jobs),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

            log.info(
                "job_discovery_completed",
                user_id=str(user_id),
                query=query,
                found=len(saved_jobs),
            )

            return {
                "search_run_id": run_id,
                "jobs_count": len(saved_jobs),
                "cached": False,
                "jobs": saved_jobs,
            }

        except Exception as exc:
            log.error("job_discovery_failed", user_id=str(user_id), error=str(exc))
            if run_id:
                await self.job_repo.update_search_run(
                    run_id=run_id,
                    updates={
                        "status": "failed",
                        "error_summary": str(exc),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

            # Fallback: return any existing cached jobs matching query
            cached = await self.job_repo.list_jobs(query=query, remote_only=remote_only, limit=30)
            return {
                "search_run_id": run_id,
                "jobs_count": len(cached),
                "cached": True,
                "jobs": cached,
            }
