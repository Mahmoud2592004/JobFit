"""
LinkedIn Jobs Scraper Provider via Apify.

Integrates with the `curious_coder/linkedin-jobs-scraper` Actor on Apify:
https://apify.com/curious_coder/linkedin-jobs-scraper/input-schema

Optimizes scraper input using candidate preferences and profile experience
(seniority, keywords, target roles, preferred location, remote status, under-10 applicants,
and publication freshness) in accordance with LinkedIn's AI job search architecture.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
import structlog

from app.core.config import Settings
from app.providers.jobs.base import JobProvider
from app.schemas.job import CanonicalJob
from app.services.html_sanitizer import strip_html_to_text

log = structlog.get_logger(__name__)

DEFAULT_ACTOR_ID = "curious_coder~linkedin-jobs-scraper"
APIFY_API_BASE_URL = "https://api.apify.com/v2/acts"
MAX_APIFY_LIMIT = 10


def parse_linkedin_salary(
    salary_info: Any,
) -> tuple[int | None, int | None, str | None]:
    """
    Extract normalized min, max salary and currency from LinkedIn salary info.
    salary_info can be a list of strings (e.g. ["$120,000", "$150,000"]) or a string.
    """
    if not salary_info:
        return None, None, None

    combined_text = ""
    if isinstance(salary_info, list):
        combined_text = " ".join(str(s) for s in salary_info)
    elif isinstance(salary_info, str):
        combined_text = salary_info
    else:
        return None, None, None

    currency = (
        "USD"
        if "$" in combined_text
        else ("EUR" if "€" in combined_text else ("GBP" if "£" in combined_text else None))
    )

    # Extract numeric amounts (e.g. 120,000 or 120k)
    matches = re.findall(r"(\d+(?:,\d+)*(?:\.\d+)?)\s*([kK])?", combined_text)
    if not matches:
        return None, None, currency

    amounts: list[int] = []
    for num_str, k_suffix in matches:
        try:
            val = float(num_str.replace(",", ""))
            if k_suffix:
                val *= 1000
            # If rate is hourly (e.g., $15 - $25), keep integer value
            amounts.append(int(val))
        except ValueError:
            continue

    if not amounts:
        return None, None, currency

    if len(amounts) == 1:
        return amounts[0], None, currency

    return min(amounts[0], amounts[1]), max(amounts[0], amounts[1]), currency


def parse_linkedin_date(
    posted_at: Any,
    posted_timestamp: Any = None,
) -> datetime | None:
    """Parse publication date from string or epoch milliseconds timestamp."""
    if posted_timestamp is not None:
        try:
            ts = float(posted_timestamp)
            # If timestamp in milliseconds (13 digits)
            if ts > 1e11:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            pass

    if isinstance(posted_at, str) and posted_at.strip():
        clean = posted_at.strip()
        # Try ISO 8601
        try:
            return datetime.fromisoformat(clean.replace("Z", "+00:00"))
        except ValueError:
            pass
        # Try YYYY-MM-DD
        try:
            return datetime.strptime(clean, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


class LinkedInApifyProvider(JobProvider):
    """
    Job provider using Apify's curious_coder/linkedin-jobs-scraper actor.
    Conforms to the JobProvider protocol.
    """

    name = "linkedin_apify"

    def __init__(
        self,
        api_token: str | None = None,
        actor_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        settings = Settings()
        self.api_token = api_token if api_token is not None else settings.apify_api_token
        self.actor_id = actor_id or settings.apify_actor_id or DEFAULT_ACTOR_ID
        self.timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else float(settings.apify_timeout_seconds)
        )

    def build_actor_input(
        self,
        query: str | None = None,
        limit: int = 50,
        preferences: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Synthesize Apify actor input adhering strictly to curious_coder/linkedin-jobs-scraper:
        - urls: Array of LinkedIn search URLs. When provided, AI search filters below are ignored.
        - keywords: Free-text search or job title
        - location: City, region, or country (e.g. 'United States', 'London, United Kingdom', 'Remote', 'Cairo, Egypt')
        - geoId: Optional LinkedIn geoId for precise location targeting
        - distance: Search radius in miles around location
        - datePosted: 'anyTime', 'past24Hours', 'pastWeek', 'pastMonth'
        - companyIds: Array of numeric company IDs
        - under10Applicants: Only jobs with fewer than 10 applicants
        - autoConvertToAiSearch: Boolean (default: true)
        - scrapeCompany: Boolean (default: true)
        - limitPerSource: Max jobs to scrape
        - splitByLocation: Boolean
        - splitCountry: Country code string (e.g. 'EG', 'US', 'GB')
        """
        prefs = preferences or {}

        # 1. Direct Search URLs
        raw_urls = prefs.get("urls") or []
        urls: list[str] = [raw_urls] if isinstance(raw_urls, str) else list(raw_urls)
        urls = [u.strip() for u in urls if isinstance(u, str) and u.strip()]

        # 2. Keywords
        raw_query = (query or "").strip()
        if not raw_query:
            raw_query = str(prefs.get("keywords") or "").strip()
        if not raw_query:
            target_roles = prefs.get("target_roles") or prefs.get("preferred_job_titles") or []
            if target_roles:
                raw_query = str(target_roles[0]).strip()
        if not raw_query:
            raw_query = "Software Engineer"

        # Seniority Enrichment
        seniority_levels_list = prefs.get("seniority_levels") or []
        fallback_level = seniority_levels_list[0] if seniority_levels_list else ""
        seniority_level = str(prefs.get("seniority_level") or fallback_level).lower()
        years_exp = float(prefs.get("years_experience") or 0.0)

        seniority_prefix = ""
        lower_query = raw_query.lower()
        has_seniority_term = any(
            t in lower_query for t in ("senior", "lead", "principal", "junior", "staff")
        )
        if not has_seniority_term:
            if years_exp >= 5 or seniority_level in {"lead", "principal", "staff", "senior"}:
                seniority_prefix = "Senior"
            elif 0 < years_exp <= 2 or seniority_level in {"junior", "entry"}:
                seniority_prefix = "Junior"

        # Skills Enrichment (pick top 2 relevant skills if not already in query)
        extra_skills: list[str] = []
        candidate_skills = prefs.get("skills") or prefs.get("keywords_include") or []
        for sk in candidate_skills:
            sk_clean = str(sk).strip()
            if sk_clean and sk_clean.lower() not in lower_query and len(extra_skills) < 2:
                extra_skills.append(sk_clean)

        work_arrangements = [str(w).lower() for w in prefs.get("work_arrangements", [])]
        is_remote_preferred = (
            "remote" in work_arrangements
            or prefs.get("remote_only") is True
        )
        remote_keyword = "Remote" if (is_remote_preferred and "remote" not in lower_query) else ""

        keyword_parts = [part for part in [seniority_prefix, raw_query, " ".join(extra_skills), remote_keyword] if part]
        keywords_str = " ".join(keyword_parts).strip()

        # 3. Location: Strictly prioritize user-specified location without overwriting it!
        location_val = ""
        if prefs.get("location") and str(prefs["location"]).strip():
            location_val = str(prefs["location"]).strip()
        elif prefs.get("locations"):
            loc_list = prefs["locations"]
            if isinstance(loc_list, list) and loc_list:
                location_val = str(loc_list[0]).strip()
            elif isinstance(loc_list, str):
                location_val = loc_list.strip()

        # If user did not provide an explicit location, default to "Remote"
        if not location_val or location_val.lower() == "any":
            location_val = "Remote"

        # 4. datePosted
        date_posted = prefs.get("date_posted") or prefs.get("datePosted") or "pastMonth"
        valid_dates = {"past24Hours", "pastWeek", "pastMonth", "anyTime"}
        if date_posted not in valid_dates:
            date_posted = "pastMonth"

        # 5. under10Applicants
        under_10 = bool(
            prefs.get("under_10_applicants")
            or prefs.get("under10Applicants", False)
        )

        # 6. limitPerSource
        raw_limit = limit if limit is not None else (
            prefs.get("limit_per_source") or prefs.get("limitPerSource") or 35
        )
        capped_limit = min(max(int(raw_limit), 1), MAX_APIFY_LIMIT)

        actor_payload: dict[str, Any] = {
            "urls": urls,
            "keywords": keywords_str,
            "location": location_val,
            "datePosted": date_posted,
            "under10Applicants": under_10,
            "autoConvertToAiSearch": bool(
                prefs.get("auto_convert_to_ai_search", prefs.get("autoConvertToAiSearch", True))
            ),
            "scrapeCompany": bool(
                prefs.get("scrape_company", prefs.get("scrapeCompany", False))
            ),
            "limitPerSource": capped_limit,
            "splitByLocation": bool(
                prefs.get("split_by_location", prefs.get("splitByLocation", False))
            ),
        }

        # Optional LinkedIn parameters
        if prefs.get("geo_id") or prefs.get("geoId"):
            actor_payload["geoId"] = str(prefs.get("geo_id") or prefs.get("geoId"))
        if prefs.get("distance") is not None:
            try:
                actor_payload["distance"] = int(prefs["distance"])
            except (ValueError, TypeError):
                pass
        if prefs.get("company_ids") or prefs.get("companyIds"):
            c_ids = prefs.get("company_ids") or prefs.get("companyIds")
            actor_payload["companyIds"] = list(c_ids) if isinstance(c_ids, list) else [str(c_ids)]
        if prefs.get("split_country") or prefs.get("splitCountry"):
            actor_payload["splitCountry"] = str(prefs.get("split_country") or prefs.get("splitCountry"))

        return actor_payload

    def normalize_job(self, item: dict[str, Any]) -> CanonicalJob:
        """Map raw LinkedIn scraper dataset item into CanonicalJob schema."""
        raw_id = str(item.get("id") or item.get("link") or uuid4())
        canonical_url = str(item.get("link") or item.get("applyUrl") or "")
        title = str(item.get("title") or "Untitled Position").strip()
        employer = str(item.get("companyName") or "Confidential").strip()
        location = item.get("location")

        # Inferred work arrangement
        work_arrangement: str | None = None
        workplace_types = item.get("workplaceTypes") or []
        if isinstance(workplace_types, str):
            workplace_types = [workplace_types]
        types_lower = [str(w).lower() for w in workplace_types]

        # Description text
        desc = item.get("descriptionText")
        if not desc and item.get("descriptionHtml"):
            desc = strip_html_to_text(item["descriptionHtml"])
        description = str(desc or title).strip()

        full_text = f"{title} {location or ''} {description}".lower()
        input_url = str(item.get("inputUrl") or "").lower()

        is_hybrid = any("hybrid" in w for w in types_lower) or "hybrid" in full_text
        is_onsite = (
            any("on-site" in w or "onsite" in w for w in types_lower) or "on-site" in full_text
        )
        is_remote = (
            item.get("workRemoteAllowed") is True
            or any("remote" in w for w in types_lower)
            or any(kw in full_text for kw in ("remote", "work from home", "telecommute"))
            or "location=remote" in input_url
            or ("keywords=" in input_url and "remote" in input_url)
            or (bool(location) and "remote" in str(location).lower())
        )

        if is_hybrid:
            work_arrangement = "hybrid"
        elif is_remote:
            work_arrangement = "remote"
        elif is_onsite:
            work_arrangement = "onsite"

        # Employment type
        raw_emp = str(item.get("employmentType") or "").lower()
        employment_type: str | None = None
        if "full" in raw_emp:
            employment_type = "full_time"
        elif "part" in raw_emp:
            employment_type = "part_time"
        elif "contract" in raw_emp or "temp" in raw_emp:
            employment_type = "contract"
        elif "intern" in raw_emp:
            employment_type = "internship"

        # Salary parsing (check both salaryInfo and salary fields)
        raw_sal = item.get("salaryInfo") or item.get("salary")
        sal_min, sal_max, currency = parse_linkedin_salary(raw_sal)

        # Published timestamp
        published_at = parse_linkedin_date(
            item.get("postedAt"),
            item.get("postedAtTimestamp"),
        )

        return CanonicalJob(
            source_name=self.name,
            source_job_id=raw_id,
            canonical_url=canonical_url,
            title=title,
            employer=employer,
            location=location,
            work_arrangement=work_arrangement,  # type: ignore[arg-type]
            employment_type=employment_type,  # type: ignore[arg-type]
            seniority=item.get("seniorityLevel"),
            description=description,
            salary_min=sal_min,
            salary_max=sal_max,
            salary_currency=currency,
            published_at=published_at,
            attribution="LinkedIn via Apify (curious_coder/linkedin-jobs-scraper)",
        )

    async def fetch_jobs(
        self,
        query: str | None = None,
        limit: int = MAX_APIFY_LIMIT,
        preferences: dict[str, Any] | None = None,
    ) -> list[CanonicalJob]:
        """
        Execute synchronous Actor run on Apify and return normalized CanonicalJobs.
        Handles errors gracefully and returns empty list on network or configuration failure.
        """
        if not self.api_token:
            log.warning(
                "apify_api_token_not_configured",
                detail="APIFY_API_TOKEN is empty. Set it in .env to enable live scraping.",
            )
            return []

        payload = self.build_actor_input(query=query, limit=limit, preferences=preferences)
        limit_per_source = int(payload.get("limitPerSource", MAX_APIFY_LIMIT))
        endpoint = f"{APIFY_API_BASE_URL}/{self.actor_id}/run-sync-get-dataset-items"
        params = {
            "token": self.api_token,
            "timeout": int(self.timeout),
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "JobFit-Platform/1.0 (Apify-LinkedIn-Scraper)",
        }

        try:
            # Client timeout slightly higher than Apify timeout so Apify returns first
            async with httpx.AsyncClient(timeout=self.timeout + 10.0) as client:
                log.info(
                    "apify_linkedin_fetch_starting",
                    keywords=payload.get("keywords"),
                    location=payload.get("location"),
                    limit=payload.get("limitPerSource"),
                )
                response = await client.post(
                    endpoint,
                    params=params,
                    json=payload,
                    headers=headers,
                )

                if response.status_code != 200 and response.status_code != 201:
                    log.warning(
                        "apify_linkedin_fetch_non_200",
                        status_code=response.status_code,
                        detail=response.text[:300],
                    )
                    return []

                data = response.json()
                if not isinstance(data, list):
                    log.warning(
                        "apify_linkedin_unexpected_response_format",
                        data_type=type(data).__name__,
                    )
                    return []

                jobs: list[CanonicalJob] = []
                for item in data[:limit_per_source]:
                    if not isinstance(item, dict):
                        continue
                    try:
                        jobs.append(self.normalize_job(item))
                    except Exception as parse_err:
                        log.debug("apify_item_normalization_failed", error=str(parse_err))

                log.info(
                    "apify_linkedin_fetch_success",
                    scraped_count=len(jobs),
                    keywords=payload.get("keywords"),
                )
                return jobs

        except httpx.TimeoutException:
            log.warning("apify_linkedin_fetch_timeout", timeout=self.timeout)
            return []
        except Exception as exc:
            log.warning("apify_linkedin_fetch_failed", error=str(exc))
            return []
