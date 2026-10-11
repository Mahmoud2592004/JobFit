"""
Remotive Job Board Provider.
Fetches public remote job listings via Remotive API without requiring API keys.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx
import structlog

from app.providers.jobs.base import JobProvider
from app.schemas.job import CanonicalJob
from app.services.html_sanitizer import strip_html_to_text

log = structlog.get_logger(__name__)

REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"
DEFAULT_TIMEOUT_SECONDS = 10.0


def _parse_salary(salary_str: str | None) -> tuple[int | None, int | None, str | None]:
    """Extract approximate salary range and currency from unstructured text."""
    if not salary_str:
        return None, None, None

    currency = (
        "USD"
        if "$" in salary_str
        else ("EUR" if "€" in salary_str else ("GBP" if "£" in salary_str else None))
    )

    # Match numeric amounts with optional k suffix (e.g. 120k, 120,000)
    numbers = re.findall(r"(\d+(?:,\d+)*(?:\.\d+)?)\s*([kK])?", salary_str)
    if not numbers:
        return None, None, currency

    parsed_amounts: list[int] = []
    for num_text, k_suffix in numbers:
        clean_num = float(num_text.replace(",", ""))
        if k_suffix:
            clean_num *= 1000
        parsed_amounts.append(int(clean_num))

    if len(parsed_amounts) == 1:
        return parsed_amounts[0], None, currency
    if len(parsed_amounts) >= 2:
        return (
            min(parsed_amounts[0], parsed_amounts[1]),
            max(parsed_amounts[0], parsed_amounts[1]),
            currency,
        )

    return None, None, currency


class RemotiveProvider(JobProvider):
    """Client for Remotive Remote Jobs API."""

    name = "remotive"

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.timeout = timeout_seconds

    async def fetch_jobs(
        self,
        query: str | None = None,
        limit: int = 50,
        _preferences: dict[str, Any] | None = None,
    ) -> list[CanonicalJob]:
        params: dict[str, Any] = {"limit": limit}
        if query and query.strip():
            params["search"] = query.strip()

        headers = {
            "User-Agent": "JobFit-Platform/1.0 (job-discovery-engine; contact@jobfit.local)",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(REMOTIVE_API_URL, params=params, headers=headers)
                if response.status_code != 200:
                    log.warning(
                        "remotive_fetch_non_200",
                        status_code=response.status_code,
                        detail=response.text[:200],
                    )
                    return []

                payload = response.json()
        except Exception as exc:
            log.warning("remotive_fetch_failed", error=str(exc))
            return []

        raw_jobs: list[dict[str, Any]] = payload.get("jobs", [])
        canonical_jobs: list[CanonicalJob] = []

        for item in raw_jobs[:limit]:
            job_id = str(item.get("id", ""))
            if not job_id:
                continue

            pub_date: datetime | None = None
            if pub_raw := item.get("publication_date"):
                try:
                    pub_date = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
                except ValueError:
                    pub_date = None

            sal_min, sal_max, sal_curr = _parse_salary(item.get("salary"))

            # Normalize employment type
            raw_type = str(item.get("job_type", "")).lower()
            if "full" in raw_type:
                emp_type = "full_time"
            elif "contract" in raw_type or "freelance" in raw_type:
                emp_type = "contract"
            elif "part" in raw_type:
                emp_type = "part_time"
            elif "intern" in raw_type:
                emp_type = "internship"
            else:
                emp_type = None

            canonical_jobs.append(
                CanonicalJob(
                    source_name=self.name,
                    source_job_id=job_id,
                    canonical_url=item.get("url") or f"https://remotive.com/jobs/{job_id}",
                    title=item.get("title") or "Untitled Position",
                    employer=item.get("company_name") or "Unknown Employer",
                    location=item.get("candidate_required_location") or "Worldwide",
                    work_arrangement="remote",
                    employment_type=emp_type,
                    seniority=None,
                    description=strip_html_to_text(item.get("description")),
                    salary_min=sal_min,
                    salary_max=sal_max,
                    salary_currency=sal_curr,
                    published_at=pub_date,
                    attribution="Jobs powered by Remotive (remotive.com)",
                )
            )

        log.info("remotive_fetch_success", query=query, count=len(canonical_jobs))
        return canonical_jobs
