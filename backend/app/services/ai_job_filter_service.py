"""
AI Job Matcher and Gemini-Powered Filter Service.

Searches for jobs aligned with candidate experience and filters/validates them
using Gemini LLM structured reasoning against candidate verified experience and preferences.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

import structlog

from app.providers.llm import get_llm_adapter
from app.providers.llm.base import LLMAdapter
from app.repositories.job_repository import JobRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.search_preferences_repository import SearchPreferencesRepository
from app.schemas.job import (
    JobAIEvaluation,
    JobAIEvaluationBatch,
    JobAIFilteredItem,
    JobAIFilterResponse,
    JobResponse,
)
from app.services.matching_service import _extract_required_years

log = structlog.get_logger(__name__)

def _extract_qualifications_section(description: str) -> str:
    """Extract requirements or qualifications section from description if present."""
    if not description:
        return ""
    pattern = re.compile(
        r"(?:(?:requirements|qualifications|what we(?:\'re| are) looking for|what you(?:\'ll| will) need|who you are|minimum qualifications|preferred qualifications|skills & experience|what you bring)[\s\:\-]+)(.*?)(?=(?:\n\s*(?:benefits|what we offer|perks|about us|company overview|compensation|how to apply|\Z)))",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(description)
    if match:
        snippet = match.group(1).strip()
        if len(snippet) > 30:
            return snippet
    return description[:1000]


_AI_FILTER_SYSTEM_PROMPT = """
You are an expert technical executive recruiter and talent match evaluator.
Your role is to rigorously evaluate candidate fit against job listings using their complete descriptions and specific qualifications.

EVALUATION CRITERIA:
1. EXPERIENCE & QUALIFICATIONS ALIGNMENT:
   - Rigorously check candidate's verified years of experience and level against the role's requirements and qualifications section.
   - Junior/Entry (< 2 yrs), Mid (2-5 yrs), Senior (5-8 yrs), Lead/Principal/Staff (8+ yrs).
   - If a role demands 3+ or 5+ years and candidate has 1.5 years, clearly state this gap and reflect it in the score.
2. PREFERENCE ALIGNMENT:
   - Compare job work arrangement (remote, hybrid, onsite) and location against candidate preferences.
   - If candidate wants Remote and role is strictly Onsite elsewhere, mark as Disqualified.
3. FIT VERDICT:
   - "Strong Fit": Candidate meets or exceeds requirements and listing aligns with preferences.
   - "Potential Fit": Acceptable overlap or slight experience/skills stretch worth applying for.
   - "Not a Fit": Severe mismatch on years of experience, core tech stack, or location/remote mode.
4. HONEST, GROUNDED RATIONALE:
   - Provide a concise 1-2 sentence recruiter rationale without marketing fluff.
"""


class AIJobFilterService:
    """Service orchestrating experience-grounded job search and Gemini AI validation."""

    def __init__(
        self,
        job_repo: JobRepository,
        profile_repo: ProfileRepository,
        preferences_repo: SearchPreferencesRepository,
        llm_adapter: LLMAdapter | None = None,
    ) -> None:
        self.job_repo = job_repo
        self.profile_repo = profile_repo
        self.preferences_repo = preferences_repo
        self.llm = llm_adapter or get_llm_adapter()

    async def filter_jobs_for_candidate(
        self,
        user_id: UUID | str,
        query: str | None = None,
        location: str | None = None,
        work_arrangement: str | None = None,
        date_posted: str | None = None,
        experience_level: str | None = None,
        employment_type: str | None = None,
        min_fit: str = "valid_only",
        limit: int = 15,
    ) -> JobAIFilterResponse:
        """
        Search jobs related to candidate background and evaluate them with Gemini.
        """
        uid = str(user_id)

        # 1. Fetch candidate profile and active profile version
        prof = await self.profile_repo.get_profile(uid) or {}
        active_ver = await self.profile_repo.get_active_profile_version(uid) or {}
        prefs = await self.preferences_repo.get_preferences(uid) or {}

        years_exp = float(
            active_ver.get("years_experience")
            or prof.get("years_experience")
            or prefs.get("years_experience")
            or 0.0
        )
        seniority = str(active_ver.get("seniority_level") or "mid").lower()
        skills = [str(s) for s in active_ver.get("skills", [])]
        target_roles = [str(r) for r in active_ver.get("target_roles", [])]
        if not target_roles and prefs.get("target_roles"):
            target_roles = [str(r) for r in prefs["target_roles"]]

        # Preferred arrangements & locations
        work_arrangements = prefs.get("work_arrangements") or ["remote"]
        if work_arrangement and work_arrangement.lower() != "any":
            work_arrangements = [work_arrangement.lower()]
        preferred_locations = prefs.get("locations") or []
        if location and location.lower() not in {"any", "worldwide", "all"}:
            if location not in preferred_locations:
                preferred_locations = [location] + preferred_locations

        candidate_summary = {
            "display_name": prof.get("display_name") or "Candidate",
            "years_experience": years_exp,
            "seniority_level": seniority,
            "target_roles": target_roles,
            "top_skills": skills[:12],
            "preferred_work_arrangements": work_arrangements,
            "preferred_locations": preferred_locations,
        }

        # 2. Query matching jobs from the catalog
        search_query = query
        if not search_query and target_roles:
            search_query = target_roles[0]

        catalog_records = await self.job_repo.list_jobs(
            query=search_query,
            location=location,
            work_arrangement=work_arrangement,
            employment_type=employment_type,
            seniority=experience_level,
            date_posted=date_posted,
            limit=limit,
        )

        if not catalog_records:
            # Fallback to general listings
            catalog_records = await self.job_repo.list_jobs(limit=limit)

        jobs_by_id: dict[str, JobResponse] = {
            str(r["id"]): JobResponse.model_validate(r) for r in catalog_records
        }

        if not jobs_by_id:
            return JobAIFilterResponse(
                candidate_summary=candidate_summary,
                total_evaluated=0,
                valid_count=0,
                results=[],
            )

        # 3. Formulate Prompt for Gemini
        evaluations = await self._evaluate_with_llm(
            candidate_summary=candidate_summary,
            jobs=list(jobs_by_id.values()),
        )

        # Map back evaluations to jobs
        evaluated_items: list[JobAIFilteredItem] = []
        for eval_item in evaluations:
            job_obj = jobs_by_id.get(eval_item.job_id)
            if not job_obj:
                continue

            # Apply min_fit filter
            if min_fit == "strong_only" and eval_item.fit_level != "Strong Fit":
                continue
            if min_fit == "valid_only" and not eval_item.is_valid_match:
                continue

            evaluated_items.append(JobAIFilteredItem(job=job_obj, evaluation=eval_item))

        # Sort by ai_score descending
        evaluated_items.sort(key=lambda x: x.evaluation.ai_score, reverse=True)

        valid_count = sum(
            1 for item in evaluated_items if item.evaluation.is_valid_match
        )

        # Record search run in history
        search_run_id = None
        try:
            active_vid = active_ver.get("id") if active_ver else None
            run_record = await self.job_repo.create_search_run(
                user_id=uid,
                profile_version_id=active_vid,
                preferences_snapshot={
                    "query": query or (target_roles[0] if target_roles else "All Roles"),
                    "location": location,
                    "work_arrangement": work_arrangement,
                    "date_posted": date_posted,
                    "experience_level": experience_level,
                    "employment_type": employment_type,
                    "min_fit": min_fit,
                    "target_roles": target_roles,
                    "candidate_summary": candidate_summary,
                },
                providers_used=["gemini", "catalog"],
            )
            if run_record and run_record.get("id"):
                search_run_id = run_record["id"]
                await self.job_repo.update_search_run(
                    run_id=search_run_id,
                    updates={
                        "status": "completed",
                        "jobs_found": len(jobs_by_id),
                        "matches_created": valid_count,
                    },
                )
        except Exception as e:
            log.warning("ai_filter_save_search_run_failed", error=str(e))

        return JobAIFilterResponse(
            candidate_summary=candidate_summary,
            total_evaluated=len(jobs_by_id),
            valid_count=valid_count,
            results=evaluated_items,
            search_run_id=search_run_id,
            query=query or (target_roles[0] if target_roles else "All Roles"),
        )

    async def _evaluate_with_llm(
        self,
        candidate_summary: dict[str, Any],
        jobs: list[JobResponse],
    ) -> list[JobAIEvaluation]:
        """Call Gemini to evaluate listings with full descriptions and extracted requirements."""
        jobs_payload = [
            {
                "id": str(j.id),
                "title": j.title,
                "employer": j.employer,
                "location": j.location or "Unspecified",
                "work_arrangement": j.work_arrangement or "remote",
                "employment_type": j.employment_type or "Full-time",
                "seniority": j.seniority or "Not specified",
                "qualifications_and_requirements": _extract_qualifications_section(j.description),
                "full_description": j.description.strip(),
            }
            for j in jobs
        ]

        roles_str = ", ".join(candidate_summary["target_roles"]) or "Software Engineer"
        skills_str = ", ".join(candidate_summary["top_skills"])
        modes_str = ", ".join(candidate_summary["preferred_work_arrangements"])
        locs_str = ", ".join(candidate_summary["preferred_locations"]) or "Any"

        prompt = (
            f"CANDIDATE BACKGROUND:\n"
            f"- Verified Years of Experience: {candidate_summary['years_experience']} years\n"
            f"- Seniority Level: {candidate_summary['seniority_level']}\n"
            f"- Target Roles: {roles_str}\n"
            f"- Top Skills: {skills_str}\n"
            f"- Preferred Work Arrangements: {modes_str}\n"
            f"- Preferred Locations: {locs_str}\n\n"
            f"JOB LISTINGS TO EVALUATE:\n{jobs_payload}\n\n"
            f"Evaluate each job listing in the provided list and output the structured JSON "
            f"evaluations containing each job's id, fit_level, is_valid_match, ai_score, "
            f"experience_fit_analysis, preference_fit_analysis, and recruiter_rationale.\n"
            f"Ensure to strictly check the qualifications and requirements section against the candidate's verified background."
        )

        try:
            batch = await self.llm.extract_structured(
                prompt=prompt,
                response_model=JobAIEvaluationBatch,
                system_instruction=_AI_FILTER_SYSTEM_PROMPT,
            )
            if batch.evaluations:
                return batch.evaluations
        except Exception as exc:
            log.warning("gemini_job_filter_fallback", error=str(exc))

        # Deterministic rule-based fallback if LLM is mock or throws
        return self._deterministic_fallback_evaluation(candidate_summary, jobs)

    def _deterministic_fallback_evaluation(
        self,
        candidate_summary: dict[str, Any],
        jobs: list[JobResponse],
    ) -> list[JobAIEvaluation]:
        """Deterministic evaluation fallback ensuring zero disruption."""
        evals: list[JobAIEvaluation] = []
        cand_years = float(candidate_summary.get("years_experience", 0.0))
        cand_skills = {str(s).lower() for s in candidate_summary.get("top_skills", [])}
        work_modes = {
            str(m).lower() for m in candidate_summary.get("preferred_work_arrangements", [])
        }

        for j in jobs:
            title_lower = j.title.lower()
            job_mode = str(j.work_arrangement or "remote").lower()
            desc_lower = j.description.lower()

            # 1. Experience check
            req_years = _extract_required_years(desc_lower, title_lower)
            is_senior = any(
                w in title_lower for w in ["senior", "lead", "staff", "principal", "architect"]
            )
            is_junior = any(
                w in title_lower for w in ["junior", "entry", "intern", "associate"]
            )

            score = 70
            if req_years is not None:
                if cand_years >= req_years:
                    score += 18
                    exp_analysis = (
                        f"Candidate's {cand_years:.1f} years satisfies requirement ({req_years:g}+ yrs)."
                    )
                elif cand_years >= req_years - 1.0:
                    score += 5
                    exp_analysis = (
                        f"Candidate has {cand_years:.1f} years; role requires {req_years:g}+ years."
                    )
                else:
                    score -= 25
                    exp_analysis = (
                        f"Role requires {req_years:g}+ years experience; candidate profile has {cand_years:.1f} years."
                    )
            elif is_senior:
                if cand_years >= 5.0:
                    score += 18
                    exp_analysis = (
                        f"Candidate's {cand_years:.1f} years satisfies senior requirements."
                    )
                elif cand_years >= 3.0:
                    score += 5
                    exp_analysis = (
                        f"Candidate has {cand_years:.1f} years; role prefers 5+ years experience."
                    )
                else:
                    score -= 25
                    exp_analysis = (
                        f"Senior role seeks 5+ years; candidate has {cand_years:.1f} years."
                    )
            elif is_junior:
                if cand_years <= 3.0:
                    score += 15
                    exp_analysis = (
                        f"Candidate's {cand_years:.1f} years experience fits early-career level."
                    )
                else:
                    score += 5
                    exp_analysis = "Candidate is experienced for an entry-level position."
            else:
                score += 12 if cand_years >= 2.0 else 0
                exp_analysis = f"Experience ({cand_years:.1f} yrs) fits mid-level baseline."

            # 2. Preference check
            if "remote" in work_modes and job_mode == "remote":
                score += 10
                pref_analysis = "Fully remote position aligns directly with preferences."
            elif job_mode in work_modes or not work_modes:
                score += 5
                pref_analysis = f"Work mode '{job_mode}' matches preferences."
            else:
                score -= 22
                pref_analysis = (
                    f"Work mode '{job_mode}' differs from preferred ({', '.join(work_modes)})."
                )

            # 3. Skills check
            matched_skills = [
                s for s in cand_skills if re.search(rf"\b{re.escape(s)}\b", desc_lower)
            ]
            if matched_skills:
                score += min(15, len(matched_skills) * 3)
            else:
                score -= 8

            final_score = max(20, min(98, score))
            if final_score >= 80:
                fit_level = "Strong Fit"
                is_valid = True
                rationale = (
                    f"Strong alignment across experience level and core skills at {j.employer}."
                )
            elif final_score >= 62:
                fit_level = "Potential Fit"
                is_valid = True
                rationale = (
                    f"Viable opportunity at {j.employer}; review specific tech requirements."
                )
            else:
                fit_level = "Not a Fit"
                is_valid = False
                rationale = (
                    f"Not recommended: gap in experience expectations or work mode at {j.employer}."
                )

            evals.append(
                JobAIEvaluation(
                    job_id=str(j.id),
                    is_valid_match=is_valid,
                    fit_level=fit_level,
                    ai_score=final_score,
                    experience_fit_analysis=exp_analysis,
                    preference_fit_analysis=pref_analysis,
                    recruiter_rationale=rationale,
                )
            )

        return evals
