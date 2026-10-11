"""
Transparent Profile-Job Matching & Explainability Engine (v1.0.0).
Computes deterministic, multi-factor compatibility scores and grounded explanations.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog

from app.repositories.job_match_repository import JobMatchRepository
from app.repositories.job_repository import JobRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.match import ScoreBreakdown

log = structlog.get_logger(__name__)

SCORING_VERSION = "v1.0.0"

_COMMON_TECH_SKILLS = {
    "python",
    "javascript",
    "typescript",
    "react",
    "next.js",
    "vue",
    "angular",
    "node.js",
    "fastapi",
    "django",
    "flask",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "sql",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "graphql",
    "rest",
    "git",
    "ci/cd",
    "linux",
    "terraform",
    "html",
    "css",
    "tailwind",
    "go",
    "golang",
    "rust",
    "c++",
    "c#",
    "java",
    "spring",
    "kafka",
    "pandas",
    "pytorch",
    "tensorflow",
}


def _tokenize(text: str) -> set[str]:
    """Extract clean lowercase tokens from text."""
    clean = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return {w for w in clean.split() if len(w) > 2}


def _extract_required_years(desc: str, title: str = "") -> float | None:
    """
    Extract the minimum required years of experience from job description and title.
    Handles phrasing such as:
      - '3+ years of experience in machine learning'
      - 'at least 3 years experience'
      - '2-5 years of experience' -> 2.0
      - 'minimum 4 years of professional experience'
      - 'experience: 3+ years'
    """
    text = f"{title}\n{desc}".lower()

    patterns = [
        # "-  3+ years of experience in machine learning engineering", "at least 3 years experience", "2-5 years of experience"
        r"(?:(?:at least|minimum of|minimum|min\.?)\s+)?(\d+(?:\.\d+)?)\s*(?:\+|plus)?\s*(?:-|to|\+)?\s*(?:\d+)?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp|in\s+machine|in\s+data|in\s+software|in\s+ai|relevant|professional|practical)",
        # "experience: 3+ years", "experience of 3+ years", "experience: 3 years"
        r"experience\s*(?:of)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:\+|plus)?\s*(?:years?|yrs?)",
        # "3+ years working with/as/in"
        r"(\d+(?:\.\d+)?)\s*(?:\+|plus)?\s*(?:years?|yrs?)\s+(?:working\s+(?:with|as|in)|building|developing|in\s+a\s+role)",
    ]

    extracted: list[float] = []
    for pat in patterns:
        for match in re.finditer(pat, text):
            try:
                val = float(match.group(1))
                if 1.0 <= val <= 15.0:
                    extracted.append(val)
            except (ValueError, IndexError):
                continue

    if extracted:
        return min(extracted)

    title_lower = title.lower()
    if any(w in title_lower for w in ["lead", "principal", "director", "head"]):
        return 6.0
    if any(w in title_lower for w in ["senior", "sr."]):
        return 5.0
    if any(w in title_lower for w in ["junior", "jr.", "entry", "associate", "intern", "trainee"]):
        return 1.0

    return None


class MatchingService:
    """Service orchestrating candidate-job compatibility scoring and explainability."""

    def __init__(
        self,
        match_repo: JobMatchRepository,
        job_repo: JobRepository,
        profile_repo: ProfileRepository,
        preferences_repo: Any = None,
    ) -> None:
        self.match_repo = match_repo
        self.job_repo = job_repo
        self.profile_repo = profile_repo
        if preferences_repo is None:
            from app.repositories.search_preferences_repository import SearchPreferencesRepository

            self.preferences_repo = SearchPreferencesRepository()
        else:
            self.preferences_repo = preferences_repo

    def evaluate_match_score(
        self,
        profile_data: dict[str, Any],
        job_data: dict[str, Any],
    ) -> tuple[float, ScoreBreakdown, list[str], list[str], list[str], str | None]:
        """
        Evaluate candidate profile against a job listing deterministically.
        Returns (overall_score, breakdown, matching_evidence, missing_reqs, uncertain, freshness).
        """
        # 1. Candidate attributes
        cand_skills = [str(s).lower().strip() for s in profile_data.get("skills", [])]
        cand_skills_set = set(cand_skills)
        cand_years = float(profile_data.get("years_experience") or 0.0)
        cand_seniority = str(profile_data.get("seniority_level") or "mid").lower()
        cand_target_roles = [str(r).lower().strip() for r in profile_data.get("target_roles", [])]
        cand_locations = [
            str(l).lower().strip()
            for l in profile_data.get("locations", [])
            if l and str(l).lower() != "any"
        ]
        cand_remote_only = bool(profile_data.get("remote_only", False))
        cand_work_arrangements = [
            str(w).lower().strip() for w in profile_data.get("work_arrangements", []) if w
        ]

        # 2. Job attributes
        job_title = str(job_data.get("title", ""))
        job_desc = str(job_data.get("description", "")).lower()
        job_location = str(job_data.get("location", ""))
        job_location_lower = job_location.lower()
        job_arrangement = str(job_data.get("work_arrangement", "remote")).lower()
        job_published = job_data.get("published_at")
        job_expired = bool(job_data.get("is_expired", False))

        matching_evidence: list[str] = []
        missing_requirements: list[str] = []
        uncertain_factors: list[str] = []

        # ──────────────────────────────────────────────────────────────────────────
        # Factor 1: Skills Overlap (Weight 40%)
        # ──────────────────────────────────────────────────────────────────────────
        detected_job_skills: set[str] = set()
        for skill in _COMMON_TECH_SKILLS | cand_skills_set:
            if re.search(rf"\b{re.escape(skill)}\b", job_desc):
                detected_job_skills.add(skill)

        matched_skills: list[str] = []
        unmatched_skills: list[str] = []

        for skill in detected_job_skills:
            if skill in cand_skills_set:
                matched_skills.append(skill)
            else:
                unmatched_skills.append(skill)

        if detected_job_skills:
            skills_ratio = len(matched_skills) / len(detected_job_skills)
            skills_score = min(100.0, max(20.0, skills_ratio * 100.0))
        else:
            skills_score = 75.0

        if matched_skills:
            top_matched = ", ".join(sorted(matched_skills)[:5])
            matching_evidence.append(
                f"Candidate possesses {len(matched_skills)} matching core skills: {top_matched}"
            )

        if unmatched_skills:
            top_missing = ", ".join(sorted(unmatched_skills)[:4])
            missing_requirements.append(
                f"Skills highlighted in job not found in candidate profile: {top_missing}"
            )

        # ──────────────────────────────────────────────────────────────────────────
        # Factor 2: Experience & Seniority Alignment (Weight 25%)
        # ──────────────────────────────────────────────────────────────────────────
        req_years = _extract_required_years(job_desc, job_title)

        if req_years is not None:
            if cand_years >= req_years:
                experience_score = 95.0
                matching_evidence.append(
                    f"Candidate has {cand_years:.1f} years experience, meeting role requirement ({req_years:g}+ yrs)."
                )
            elif cand_years >= req_years - 1.0:
                experience_score = 60.0
                uncertain_factors.append(
                    f"Experience stretch: role seeks {req_years:g}+ years; candidate has {cand_years:.1f} years."
                )
            else:
                experience_score = 30.0
                missing_requirements.append(
                    f"Experience gap: job requires {req_years:g}+ years of experience; candidate profile has {cand_years:.1f} years."
                )
        else:
            title_lower = job_title.lower()
            job_is_lead = any(w in title_lower for w in ["lead", "principal", "director", "head"])
            job_is_senior = any(w in title_lower for w in ["senior", "sr."])
            job_is_junior = any(
                w in title_lower for w in ["junior", "jr.", "entry", "associate", "intern", "trainee"]
            )

            if job_is_lead:
                if cand_years >= 6.0:
                    experience_score = 95.0
                    matching_evidence.append(f"Candidate meets lead experience threshold ({cand_years:.1f} yrs).")
                else:
                    experience_score = 25.0
                    missing_requirements.append(
                        f"Lead role requires 6+ years experience; candidate has {cand_years:.1f} years."
                    )
            elif job_is_senior:
                if cand_years >= 5.0 or cand_seniority in {"senior", "lead", "staff"}:
                    experience_score = 95.0
                    matching_evidence.append(
                        f"Candidate has {cand_years:.1f} years experience, meeting requirements."
                    )
                elif cand_years >= 3.0:
                    experience_score = 60.0
                    uncertain_factors.append(
                        f"Senior role seeks 5+ years; candidate has {cand_years:.1f} years."
                    )
                else:
                    experience_score = 30.0
                    missing_requirements.append(
                        f"Senior role seeks 5+ years experience; candidate has {cand_years:.1f} years."
                    )
            elif job_is_junior:
                if cand_years <= 3.0:
                    experience_score = 98.0
                    matching_evidence.append(
                        f"Junior/Entry role aligns with candidate's experience level ({cand_years:.1f} yrs)."
                    )
                else:
                    experience_score = 75.0
            else:
                if cand_years >= 2.0:
                    experience_score = 92.0
                    matching_evidence.append(f"Candidate's {cand_years:.1f} years experience aligns with role.")
                elif cand_years >= 1.0:
                    experience_score = 80.0
                    matching_evidence.append(f"Candidate has {cand_years:.1f} years experience.")
                else:
                    experience_score = 65.0

        # ──────────────────────────────────────────────────────────────────────────
        # Factor 3: Role & Title Alignment (Weight 20%)
        # ──────────────────────────────────────────────────────────────────────────
        job_title_tokens = _tokenize(job_title)
        role_score = 30.0
        role_matched = False

        if cand_target_roles:
            for target in cand_target_roles:
                target_tokens = _tokenize(target)
                overlap = job_title_tokens & target_tokens
                if overlap:
                    # Check how close the match is
                    ratio = len(overlap) / max(len(target_tokens), 1)
                    if ratio >= 0.5:
                        role_score = 98.0
                        role_matched = True
                        matching_evidence.append(f"Target role aligns with listing title: '{job_title}'")
                        break
                    elif ratio > 0:
                        role_score = max(role_score, 75.0)
                        role_matched = True

        if not role_matched:
            # Check technical relevance
            tech_keywords = {"engineer", "developer", "scientist", "ai", "ml", "software", "machine"}
            if job_title_tokens & tech_keywords:
                role_score = 60.0
            else:
                role_score = 20.0
                missing_requirements.append(f"Listing title '{job_title}' does not match target roles.")

        # ──────────────────────────────────────────────────────────────────────────
        # Factor 4: Work Arrangement & Location (Weight 15%)
        # ──────────────────────────────────────────────────────────────────────────
        work_arrangement_score = 70.0

        # Location compatibility check
        loc_matched = False
        if cand_locations:
            for c_loc in cand_locations:
                if c_loc in job_location_lower or (job_location and any(tok in job_location_lower for tok in _tokenize(c_loc))):
                    loc_matched = True
                    break

        if job_arrangement == "remote":
            if loc_matched or not cand_locations or "remote" in cand_locations or "worldwide" in job_location_lower or not job_location or job_location_lower == "remote":
                work_arrangement_score = 100.0
                matching_evidence.append("Listing is fully remote, offering maximum flexibility.")
            else:
                # Candidate specified an explicit location e.g. 'Egypt', but remote job is region-locked to another country
                work_arrangement_score = 65.0
                uncertain_factors.append(f"Remote listing specifies location base in '{job_location}'.")
        elif job_arrangement == "hybrid":
            if cand_remote_only or ("remote" in cand_work_arrangements and len(cand_work_arrangements) == 1):
                work_arrangement_score = 40.0
                missing_requirements.append("Listing is hybrid; candidate requires remote work.")
            elif loc_matched:
                work_arrangement_score = 90.0
                matching_evidence.append(f"Hybrid job located in candidate target area ({job_location}).")
            else:
                work_arrangement_score = 30.0
                missing_requirements.append(f"Hybrid position located in {job_location}, outside target location.")
        else:  # Onsite
            if cand_remote_only:
                work_arrangement_score = 15.0
                missing_requirements.append("Listing is onsite; candidate requires remote work.")
            elif loc_matched:
                work_arrangement_score = 85.0
                matching_evidence.append(f"Onsite position located in candidate target area ({job_location}).")
            else:
                work_arrangement_score = 20.0
                missing_requirements.append(f"Onsite position located in {job_location}, outside target location.")

        # ──────────────────────────────────────────────────────────────────────────
        # Freshness Warning
        # ──────────────────────────────────────────────────────────────────────────
        freshness_warning: str | None = None
        if job_expired:
            freshness_warning = "This job listing has been flagged as expired by the provider."
        elif job_published:
            try:
                if isinstance(job_published, str):
                    pub_dt = datetime.fromisoformat(job_published.replace("Z", "+00:00"))
                elif isinstance(job_published, datetime):
                    pub_dt = job_published
                else:
                    pub_dt = None

                if pub_dt:
                    age_days = (datetime.now(timezone.utc) - pub_dt).days
                    if age_days > 30:
                        freshness_warning = (
                            f"Listing was published {age_days} days ago and may be nearing closure."
                        )
            except Exception:
                freshness_warning = None

        # ──────────────────────────────────────────────────────────────────────────
        # Overall Weighted Score
        # ──────────────────────────────────────────────────────────────────────────
        overall_score = round(
            0.40 * skills_score
            + 0.25 * experience_score
            + 0.20 * role_score
            + 0.15 * work_arrangement_score,
            2,
        )

        breakdown = ScoreBreakdown(
            skills_score=round(skills_score, 2),
            experience_score=round(experience_score, 2),
            role_score=round(role_score, 2),
            work_arrangement_score=round(work_arrangement_score, 2),
        )

        return (
            overall_score,
            breakdown,
            matching_evidence,
            missing_requirements,
            uncertain_factors,
            freshness_warning,
        )

    async def match_job_for_user(
        self,
        user_id: UUID | str,
        job_id: UUID | str,
        search_run_id: UUID | str | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate compatibility of a single job for the candidate's active profile and persist.
        """
        uid = str(user_id)
        jid = str(job_id)

        # 1. Fetch Job
        job = await self.job_repo.get_job(jid)
        if not job:
            from app.core.exceptions import NotFoundError

            raise NotFoundError(resource=f"Job listing {jid}")

        # 2. Fetch Active Profile & Search Preferences
        profile_version = await self.profile_repo.get_active_profile_version(uid)
        profile_data = {}
        if profile_version:
            content = profile_version.get("content") or {}
            profile_data = {
                "skills": profile_version.get("skills") or content.get("skills") or [],
                "target_roles": profile_version.get("target_roles") or content.get("target_roles") or [],
                "years_experience": profile_version.get("years_experience") or content.get("years_experience") or 0.0,
                "seniority_level": profile_version.get("seniority_level") or content.get("seniority_level") or "mid",
                **profile_version.get("profile_data", {}),
            }

        # Merge user search preferences (locations, work arrangement, target roles, experience)
        try:
            prefs = await self.preferences_repo.get_preferences(uid)
            if prefs:
                if prefs.get("locations"):
                    profile_data["locations"] = prefs["locations"]
                elif prefs.get("location"):
                    profile_data["locations"] = [prefs["location"]]
                if prefs.get("work_arrangements"):
                    profile_data["work_arrangements"] = prefs["work_arrangements"]
                if prefs.get("remote_only") is not None:
                    profile_data["remote_only"] = prefs["remote_only"]
                if prefs.get("preferred_job_titles"):
                    combined_roles = list(dict.fromkeys(
                        list(profile_data.get("target_roles", [])) + list(prefs.get("preferred_job_titles", []))
                    ))
                    profile_data["target_roles"] = combined_roles
                if prefs.get("years_experience") is not None:
                    profile_data["years_experience"] = float(prefs["years_experience"])
        except Exception as e:
            log.warning("matching_service_load_preferences_failed", error=str(e))

        pvid = profile_version.get("id") if profile_version else None

        # 3. Compute deterministic scores
        (
            overall_score,
            breakdown,
            evidence,
            missing,
            uncertain,
            freshness,
        ) = self.evaluate_match_score(profile_data, job)

        # 4. Upsert match record
        saved_match = await self.match_repo.upsert_match(
            user_id=uid,
            job_id=jid,
            scoring_version=SCORING_VERSION,
            overall_score=overall_score,
            score_breakdown=breakdown.model_dump(),
            matching_evidence=evidence,
            missing_requirements=missing,
            uncertain_factors=uncertain,
            freshness_warning=freshness,
            search_run_id=search_run_id,
            profile_version_id=pvid,
        )

        saved_match["job"] = job
        return saved_match

    async def batch_match_jobs(
        self,
        user_id: UUID | str,
        job_ids: Sequence[UUID | str],
        search_run_id: UUID | str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Evaluate compatibility for multiple jobs in batch.
        """
        matches: list[dict[str, Any]] = []
        for jid in job_ids:
            try:
                m = await self.match_job_for_user(
                    user_id=user_id,
                    job_id=jid,
                    search_run_id=search_run_id,
                )
                matches.append(m)
            except Exception as exc:
                log.warning("batch_match_single_failed", job_id=str(jid), error=str(exc))

        return matches
