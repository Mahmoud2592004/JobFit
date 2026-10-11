"""
Arbeitnow Job Board Provider.
Fetches public European & global tech job listings via Arbeitnow API without requiring keys.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from app.providers.jobs.base import JobProvider
from app.schemas.job import CanonicalJob
from app.services.html_sanitizer import strip_html_to_text

log = structlog.get_logger(__name__)

ARBEITNOW_API_URL = "https://www.arbeitnow.com/api/job-board-api"
DEFAULT_TIMEOUT_SECONDS = 10.0


class ArbeitnowProvider(JobProvider):
    """Client for Arbeitnow Job Board API."""

    name = "arbeitnow"

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.timeout = timeout_seconds

    async def fetch_jobs(
        self,
        query: str | None = None,
        limit: int = 50,
        _preferences: dict[str, Any] | None = None,
    ) -> list[CanonicalJob]:
        params: dict[str, Any] = {}
        if query and query.strip():
            params["search"] = query.strip()

        headers = {
            "User-Agent": "JobFit-Platform/1.0 (job-discovery-engine; contact@jobfit.local)",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(ARBEITNOW_API_URL, params=params, headers=headers)
                if response.status_code != 200:
                    log.warning(
                        "arbeitnow_fetch_non_200",
                        status_code=response.status_code,
                        detail=response.text[:200],
                    )
                    return []

                payload = response.json()
        except Exception as exc:
            log.warning("arbeitnow_fetch_failed", error=str(exc))
            return []

        raw_jobs: list[dict[str, Any]] = payload.get("data", [])
        canonical_jobs: list[CanonicalJob] = []

        for item in raw_jobs[:limit]:
            slug = str(item.get("slug", ""))
            if not slug:
                continue

            pub_date: datetime | None = None
            if created_ts := item.get("created_at"):
                try:
                    if isinstance(created_ts, (int, float)):
                        pub_date = datetime.fromtimestamp(created_ts, tz=timezone.utc)
                    elif isinstance(created_ts, str):
                        pub_date = datetime.fromisoformat(created_ts.replace("Z", "+00:00"))
                except (ValueError, OSError):
                    pub_date = None

            is_remote = bool(item.get("remote"))
            arrangement = "remote" if is_remote else "hybrid"

            # Normalize job types
            types = [str(t).lower() for t in item.get("job_types", [])]
            emp_type = "full_time"
            if any("part" in t for t in types):
                emp_type = "part_time"
            elif any("contract" in t or "freelance" in t for t in types):
                emp_type = "contract"
            elif any("intern" in t for t in types):
                emp_type = "internship"

            canonical_jobs.append(
                CanonicalJob(
                    source_name=self.name,
                    source_job_id=slug,
                    canonical_url=item.get("url") or f"https://www.arbeitnow.com/jobs/{slug}",
                    title=item.get("title") or "Untitled Position",
                    employer=item.get("company_name") or "Unknown Employer",
                    location=item.get("location") or ("Remote" if is_remote else None),
                    work_arrangement=arrangement,
                    employment_type=emp_type,
                    seniority=None,
                    description=strip_html_to_text(item.get("description")),
                    salary_min=None,
                    salary_max=None,
                    salary_currency=None,
                    published_at=pub_date,
                    attribution="Jobs powered by Arbeitnow (arbeitnow.com)",
                )
            )

        log.info("arbeitnow_fetch_success", query=query, count=len(canonical_jobs))
        return canonical_jobs
