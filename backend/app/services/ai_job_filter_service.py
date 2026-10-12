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
You are an expert technical talent matcher, hiring manager, and executive recruiter.
Your objective is to evaluate each job listing against the candidate's background using comprehensive, nuanced recruiter judgment.

EVALUATION PRINCIPLES:
1. Legal Eligibility & Nationality Restrictions:
   - Carefully check the job title and description for mandatory citizenship or nationalization restrictions (e.g., "(Omani National)", "(Saudi National Only)", "(UAE National)", "(US Citizen Only)", "(Active Security Clearance Required)").
   - Compare this against the candidate's declared location/citizenship.
   - If a position legally restricts hiring to citizens of a specific nationality that conflicts with the candidate, this is an absolute disqualification. You MUST assign `ai_score` <= 20, set `fit_level = "Not a Fit"`, `is_valid_match = false`, and state the nationality restriction in `recruiter_rationale`.

2. Seniority & Experience Alignment:
   - Compare the candidate's professional tenure and seniority tier against the position's stated requirements and responsibilities.
   - If a position is designated as Senior, Lead, Principal, or Staff (in title or description) requiring deep independent ownership or multi-year enterprise leadership, an early-career candidate with ~1-2 years of experience has a major seniority deficit. Treat this as a disqualifying gap (assign `ai_score` <= 50, "Not a Fit"), regardless of whether individual technical keywords overlap.
   - Prioritize Entry-level, Junior, Graduate, or early-career roles (0-2 years) where the candidate's demonstrated project depth and skills provide an authentic, credible fit.

3. Discipline & Role Alignment:
   - Assess whether the role's primary technical discipline aligns with the candidate's targeted focus and demonstrated experience.
   - Differentiate specialized technical disciplines (e.g. AI/ML Engineering, Generative AI, Data Systems) from unrelated domains (e.g. general CMS/content web development, generic CRUD, non-technical management).
   - Roles that share only generic naming ("Developer", "Engineer") without substantive domain overlap must not be scored as strong matches.

4. Technical Competencies & Requirements Overlap:
   - Evaluate the overlap between the candidate's verified skills/projects and the role's core required tech stack, tools, and responsibilities.
   - Distinguish essential required qualifications from secondary or preferred skills.

5. Location & Work Arrangement Constraints:
   - Verify that the position respects the candidate's target locations/countries and work arrangement preferences (Remote, Hybrid, On-site). Mismatched geographic constraints must be heavily penalized.

OUTPUT SPECIFICATIONS:
- `ai_score`: A holistic match percentage from 0 to 100 based on overall recruiter evaluation.
- `fit_level`:
  * "Strong Fit" (80-100): High discipline alignment, candidate meets or closely satisfies seniority expectations, and possesses strong technical qualifications.
  * "Potential Fit" (60-79): Adjacent domain, minor experience stretch, or partial skills overlap where the candidate is viable for consideration.
  * "Not a Fit" (0-59): Substantial seniority/experience deficit, legal/nationality disqualification, mismatched discipline, or incompatible work location.
- `is_valid_match`: True if the role represents a realistic, credible match (typically ai_score >= 60), False otherwise.
- `experience_fit_analysis`: Concise, objective evaluation comparing candidate tenure and background against role requirements.
- `recruiter_rationale`: 1-2 sentences summarizing the key recruiter factors explaining the evaluation.
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
        min_fit: str = "all",
        limit: int = 30,
        candidate_profile: dict[str, Any] | None = None,
    ) -> JobAIFilterResponse:
        """
        Search jobs related to candidate background and evaluate them with Gemini.
        """
        uid = str(user_id)

        # 1. Fetch candidate profile and active profile version
        prof = await self.profile_repo.get_profile(uid) or {}
        active_ver = await self.profile_repo.get_active_profile_version(uid) or {}
        prefs = await self.preferences_repo.get_preferences(uid) or {}

        cp = candidate_profile or {}

        years_exp_raw = (
            cp.get("years_experience")
            if cp.get("years_experience") is not None
            else active_ver.get("years_experience")
            if active_ver.get("years_experience") is not None
            else prof.get("years_experience")
            if prof.get("years_experience") is not None
            else prefs.get("years_experience")
        )
        years_exp = float(years_exp_raw) if years_exp_raw is not None else None
        seniority = str(
            cp.get("seniority_level")
            or active_ver.get("seniority_level")
            or ""
        ).lower()
        skills = [str(s) for s in (active_ver.get("skills") or cp.get("skills") or [])]
        target_roles = [str(r) for r in (active_ver.get("target_roles") or cp.get("target_roles") or [])]
        if not target_roles and prefs.get("target_roles"):
            target_roles = [str(r) for r in prefs["target_roles"]]

        # Preferred arrangements & locations
        work_arrangements = prefs.get("work_arrangements") or cp.get("preferred_work_arrangements") or ["remote"]
        if work_arrangement and work_arrangement.lower() != "any":
            work_arrangements = [work_arrangement.lower()]
        preferred_locations = prefs.get("locations") or cp.get("preferred_locations") or []
        if location and location.lower() not in {"any", "worldwide", "all"}:
            if location not in preferred_locations:
                preferred_locations = [location] + preferred_locations

        cand_loc = (
            cp.get("location")
            or prof.get("location")
            or (preferred_locations[0] if preferred_locations else "Egypt")
        )
        candidate_summary = {
            "display_name": prof.get("display_name") or cp.get("display_name") or "Candidate",
            "candidate_location": cand_loc,
            "years_experience": years_exp,
            "seniority_level": seniority,
            "target_roles": target_roles,
            "top_skills": skills[:15],
            "preferred_work_arrangements": work_arrangements,
            "preferred_locations": preferred_locations,
            "work_history": (cp.get("experience") or prof.get("experience") or "")[:2000],
            "summary": (cp.get("summary") or prof.get("summary") or "")[:500],
        }

        # 2. Query matching jobs from the catalog
        target_loc_filter = location
        if not target_loc_filter and preferred_locations:
            valid_locs = [l for l in preferred_locations if l.lower() not in {"any", "worldwide", "all"}]
            if valid_locs:
                target_loc_filter = ", ".join(valid_locs)

        catalog_records = await self.job_repo.list_jobs(
            query=query,
            location=target_loc_filter,
            work_arrangement=work_arrangement,
            employment_type=employment_type,
            seniority=experience_level,
            date_posted=date_posted,
            limit=limit,
        )

        if not catalog_records or len(catalog_records) < limit:
            fallback = await self.job_repo.list_jobs(
                location=target_loc_filter,
                limit=limit,
            )
            seen_ids = {r["id"] for r in catalog_records}
            for rec in fallback:
                if rec["id"] not in seen_ids:
                    catalog_records.append(rec)
                    seen_ids.add(rec["id"])
                    if len(catalog_records) >= limit:
                        break

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
        if uid != "00000000-0000-0000-0000-000000000000":
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

        exp_years_val = candidate_summary.get("years_experience")
        if exp_years_val is not None:
            exp_declared_str = f"{exp_years_val} years (explicitly declared by candidate)"
        else:
            exp_declared_str = "Not explicitly declared (evaluate candidate's trajectory from work history and background)"

        work_hist_str = candidate_summary.get("work_history", "").strip()
        work_hist_block = f"- WORK HISTORY & EXPERIENCE:\n{work_hist_str}\n" if work_hist_str else ""
        summary_str = candidate_summary.get("summary", "").strip()
        summary_block = f"- PROFESSIONAL SUMMARY:\n{summary_str}\n" if summary_str else ""

        cand_residency = candidate_summary.get("candidate_location") or "Egypt"

        prompt = (
            f"CANDIDATE PROFILE FOR TALENT MATCHING:\n"
            f"- TARGET ROLES: {roles_str}\n"
            f"- CANDIDATE RESIDENCY & LOCATION: {cand_residency}\n"
            f"- YEARS OF EXPERIENCE: {exp_declared_str}\n"
            f"- SENIORITY LEVEL: {candidate_summary['seniority_level'] or 'Not specified'}\n"
            f"- TOP SKILLS & TECH STACK: {skills_str}\n"
            f"- PREFERRED WORK ARRANGEMENTS: {modes_str}\n"
            f"- PREFERRED LOCATIONS / COUNTRIES: {locs_str}\n"
            f"{summary_block}"
            f"{work_hist_block}\n"
            f"PRE-FILTERED JOB LISTINGS TO EVALUATE:\n{jobs_payload}\n\n"
            f"Act as a seasoned technical talent matcher and senior hiring manager. "
            f"Evaluate each job listing holistically using realistic hiring judgment (no rigid mechanical percentage formulas). "
            f"Determine a comprehensive match percentage (ai_score 0 to 100) and fit category ('Strong Fit', 'Potential Fit', 'Not a Fit'):\n"
            f"1. Legal & Nationality Restrictions: Reject jobs reserved for a specific citizenship (e.g. Omani National, Saudi Only, US Citizen) that conflicts with the candidate's residency/citizenship. Score <= 20, Not a Fit.\n"
            f"2. Seniority & Tenure Alignment: Compare role seniority against candidate tenure. If a role is Senior/Lead, an early-career candidate has a major deficit; score <= 50, Not a Fit.\n"
            f"3. Discipline & Role Alignment: Prioritize genuine roles in candidate's target technical discipline over unrelated domains (e.g. CMS/web publishing).\n"
            f"4. Technical Overlap: Assess candidate's verified skills against required qualifications.\n"
            f"5. Location & Arrangement: Verify preferred locations and remote/onsite terms match.\n\n"
            f"In `experience_fit_analysis`, provide an objective comparison of candidate background vs job requirements.\n"
            f"In `recruiter_rationale`, provide a concise 1-2 sentence recruiter summary explaining the match percentage."
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
        """Deterministic evaluation fallback scoring Title, Experience, Requirements, and Location."""
        evals: list[JobAIEvaluation] = []
        cand_years = float(candidate_summary.get("years_experience", 0.0))
        cand_skills = {str(s).lower() for s in candidate_summary.get("top_skills", [])}
        cand_roles = [str(r).lower() for r in candidate_summary.get("target_roles", [])]
        work_modes = {
            str(m).lower() for m in candidate_summary.get("preferred_work_arrangements", [])
        }
        pref_locs = [str(l).lower() for l in candidate_summary.get("preferred_locations", [])]

        for j in jobs:
            title_lower = j.title.lower()
            job_mode = str(j.work_arrangement or "remote").lower()
            job_loc_lower = str(j.location or "").lower()
            desc_lower = j.description.lower()

            # 1. Title & Seniority alignment (Max 30 pts)
            generic_archetypes = {
                "engineer", "developer", "architect", "scientist", "specialist",
                "analyst", "consultant", "manager", "lead", "senior", "junior",
                "intern", "associate", "officer", "staff", "principal", "director", "head", "vp",
            }
            cand_domain_tokens = {
                t for r in cand_roles for t in re.findall(r"[a-z0-9]+", r) if t not in generic_archetypes
            }
            title_domain_tokens = {
                t for t in re.findall(r"[a-z0-9]+", title_lower) if t not in generic_archetypes
            }

            if any(role in title_lower or title_lower in role for role in cand_roles):
                title_score = 30
            elif cand_domain_tokens and (cand_domain_tokens & title_domain_tokens):
                title_score = 25
            elif cand_domain_tokens:
                # Candidate targeted a specific discipline, but job title has generic archetype only
                title_score = 10 if any(t in title_lower for t in generic_archetypes) else 5
            elif any(eng_term in title_lower for eng_term in generic_archetypes):
                title_score = 22
            else:
                title_score = 8

            # Seniority divergence check on title
            cand_seniority = str(candidate_summary.get("seniority_level", "mid")).lower()
            is_job_senior_title = any(
                w in title_lower for w in ["senior", "lead", "staff", "principal", "architect"]
            )
            is_job_junior_title = any(
                w in title_lower for w in ["junior", "entry", "intern", "associate"]
            )
            is_cand_junior = cand_years <= 2.0 or cand_seniority in {"junior", "entry"}
            is_cand_senior = cand_years >= 4.0 or cand_seniority in {"senior", "lead", "staff", "principal"}

            if is_job_senior_title and is_cand_junior:
                title_score = max(0, title_score - 15)
            elif is_job_junior_title and is_cand_senior:
                title_score = max(0, title_score - 10)

            # 2. Years of Experience (Max 35 pts)
            req_years = _extract_required_years(desc_lower, title_lower)
            is_senior = any(
                w in title_lower for w in ["senior", "lead", "staff", "principal", "architect"]
            )
            is_junior = any(
                w in title_lower for w in ["junior", "entry", "intern", "associate"]
            )

            if req_years is not None:
                if cand_years >= req_years:
                    exp_score = 35
                    exp_analysis = f"Candidate: {cand_years:.1f} yrs | Required: {req_years:g}+ yrs | Evaluation: Met (Satisfies experience requirement)."
                elif cand_years >= req_years - 1.0:
                    exp_score = 22
                    exp_analysis = f"Candidate: {cand_years:.1f} yrs | Required: {req_years:g}+ yrs | Evaluation: Deficit of {req_years - cand_years:.1f} yrs (Close to baseline)."
                else:
                    exp_score = 8
                    exp_analysis = f"Candidate: {cand_years:.1f} yrs | Required: {req_years:g}+ yrs | Evaluation: Deficit of {req_years - cand_years:.1f} yrs (Underqualified for stated minimum)."
            elif is_senior:
                if cand_years >= 4.0:
                    exp_score = 35
                    exp_analysis = f"Candidate: {cand_years:.1f} yrs | Required: Senior level (practical 4+ yrs) | Evaluation: Met."
                elif cand_years >= 2.5:
                    exp_score = 22
                    exp_analysis = f"Candidate: {cand_years:.1f} yrs | Required: Senior level (5+ yrs) | Evaluation: Potential deficit."
                else:
                    exp_score = 8
                    exp_analysis = f"Candidate: {cand_years:.1f} yrs | Required: Senior level (5+ yrs) | Evaluation: Deficit of {5.0 - cand_years:.1f} yrs."
            elif is_junior:
                exp_score = 35
                exp_analysis = f"Candidate: {cand_years:.1f} yrs | Required: Entry level | Evaluation: Met."
            else:
                exp_score = 30 if cand_years >= 2.0 else 20
                exp_analysis = f"Candidate: {cand_years:.1f} yrs | Required: Mid level | Evaluation: Met."

            # 3. Requirements & Tech Stack Overlap (Max 35 pts)
            matched_skills = [
                s for s in cand_skills if re.search(rf"\b{re.escape(s)}\b", desc_lower)
            ]
            if len(matched_skills) >= 4:
                req_score = 35
            elif len(matched_skills) >= 2:
                req_score = 26
            elif len(matched_skills) == 1:
                req_score = 16
            else:
                req_score = 8

            # 4. Location & Work Arrangement verification
            loc_matched = True
            if pref_locs and any(pl not in {"any", "worldwide", "all"} for pl in pref_locs):
                valid_prefs = [pl for pl in pref_locs if pl not in {"any", "worldwide", "all"}]
                loc_matched = any(pl in job_loc_lower for pl in valid_prefs) or "worldwide" in job_loc_lower or (job_mode == "remote" and not job_loc_lower)

            if not loc_matched:
                pref_analysis = f"Job location '{j.location}' does not match preferred locations ({', '.join(candidate_summary.get('preferred_locations', []))})."
                loc_penalty = 35
            else:
                pref_analysis = f"Aligned with preferred location ({j.location}) and work arrangement ({job_mode})."
                loc_penalty = 0

            raw_score = title_score + exp_score + req_score - loc_penalty
            final_score = max(20, min(98, raw_score))

            if final_score >= 80 and loc_matched and exp_score >= 25:
                fit_level = "Strong Fit"
                is_valid = True
                rationale = f"Outstanding match for {j.title} based on verified {cand_years:.1f} yrs experience and strong tech stack overlap."
            elif final_score >= 60 and loc_matched:
                fit_level = "Potential Fit"
                is_valid = True
                rationale = f"Viable opportunity for {j.title} with solid qualifications; review specific tech requirements."
            else:
                fit_level = "Not a Fit"
                is_valid = False
                if not loc_matched:
                    rationale = f"Location mismatch: role based in {j.location} outside selected target countries."
                elif exp_score < 20:
                    rationale = f"Experience deficit: role seeks higher seniority than candidate's verified {cand_years:.1f} yrs."
                else:
                    rationale = f"Low alignment between role requirements and candidate's core profile."

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
