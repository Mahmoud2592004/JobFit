"""
Profile extraction service.

Coordinates:
- LLM structured extraction from resume text.
- Grounding: maps extracted claims back to verbatim source evidence.
- Creation of immutable profile versions and evidence entries.
"""

from __future__ import annotations

import difflib
from typing import Any
from uuid import UUID

import structlog

from app.providers.llm.base import LLMAdapter
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import ContactInfo, ExtractedProfile
from app.services.deterministic_parser import DeterministicResumeParser

log = structlog.get_logger(__name__)

_EXTRACTION_SYSTEM_PROMPT = """
You are an expert, factually rigorous technical resume analyzer.
Your task is to extract structured professional information from the provided candidate resume text.

CRITICAL INSTRUCTIONS:
1. ONLY extract information that is explicitly stated or clearly demonstrated in the text.
2. DO NOT invent, hallucinate, or extrapolate companies, job titles, employment dates,
   degrees, certifications, or metrics.
3. If an item (such as GPA, end date, or phone number) is not present in the text,
   leave it null or empty.
4. Extract technical and professional skills as a clean, normalized list.
5. Compute total years of professional experience conservatively based on documented
   employment dates.
6. Identify target roles that match the candidate's actual qualifications.
"""


class ProfileExtractionService:
    """Service orchestrating deterministic resume extraction and provenance grounding."""

    def __init__(
        self,
        llm: LLMAdapter | None = None,
        profile_repo: ProfileRepository | None = None,
    ) -> None:
        self.llm = llm
        self.profile_repo = profile_repo or ProfileRepository()
        self.deterministic_parser = DeterministicResumeParser()

    @staticmethod
    def _merge_extractions(det: ExtractedProfile, llm: ExtractedProfile) -> ExtractedProfile:
        """Merge deterministic extraction with LLM findings to maximize recall and precision."""
        merged_skills = sorted(set(det.skills + llm.skills))

        all_links = list(dict.fromkeys(det.contact.links + llm.contact.links))
        contact = ContactInfo(
            name=det.contact.name or llm.contact.name,
            email=det.contact.email or llm.contact.email,
            phone=det.contact.phone or llm.contact.phone,
            location=det.contact.location or llm.contact.location,
            linkedin_url=det.contact.linkedin_url or llm.contact.linkedin_url,
            portfolio_url=det.contact.portfolio_url or llm.contact.portfolio_url,
            github_url=det.contact.github_url or llm.contact.github_url,
            links=all_links,
        )

        summary = llm.summary or det.summary
        employment = det.employment_history if det.employment_history else llm.employment_history
        leadership = det.leadership if det.leadership else llm.leadership
        education = det.education if det.education else llm.education
        certs = det.certifications if det.certifications else llm.certifications
        projects = det.projects if det.projects else llm.projects
        roles = sorted(set(det.target_roles + llm.target_roles))
        seniority = det.seniority_level if det.seniority_level != "unknown" else llm.seniority_level
        years = det.years_experience if det.years_experience is not None else llm.years_experience

        return ExtractedProfile(
            contact=contact,
            summary=summary,
            skills=merged_skills if merged_skills else (det.skills or llm.skills),
            employment_history=employment,
            leadership=leadership,
            education=education,
            certifications=certs,
            projects=projects,
            target_roles=roles,
            seniority_level=seniority,
            years_experience=years,
        )

    @staticmethod
    def find_evidence_source_text(raw_text: str, claim: str) -> tuple[str | None, str]:
        """
        Locate the sentence or fragment in raw text that supports a claim.

        Returns (source_text_excerpt, confidence).
        """
        if not claim or not raw_text:
            return None, "uncertain"

        # Direct case-insensitive search
        claim_lower = claim.lower()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        for line in lines:
            if claim_lower in line.lower():
                return line, "explicit"

        # Fuzzy line match if direct substring not found
        for line in lines:
            matcher = difflib.SequenceMatcher(None, claim_lower, line.lower())
            if (
                matcher.find_longest_match(0, len(claim_lower), 0, len(line)).size
                >= len(claim_lower) * 0.8
            ):
                return line, "inferred"

        return None, "inferred"

    async def extract_and_persist_profile(
        self,
        user_id: UUID | str,
        raw_text: str,
        resume_version_id: UUID | str | None = None,
    ) -> dict[str, Any]:
        """
        Process resume text, extract structured profile deterministically, and persist to database.
        """
        uid = str(user_id)

        # 1. Deterministic extraction is primary
        extracted: ExtractedProfile = self.deterministic_parser.parse(raw_text)

        # 2. If LLM adapter is configured, optionally merge
        if self.llm:
            prompt = f"Extract structured profile information from this resume:\n\n{raw_text}"
            try:
                llm_extracted: ExtractedProfile = await self.llm.extract_structured(
                    prompt=prompt,
                    response_model=ExtractedProfile,
                    system_instruction=_EXTRACTION_SYSTEM_PROMPT,
                )
                if llm_extracted:
                    extracted = self._merge_extractions(extracted, llm_extracted)
            except Exception as exc:
                log.info("llm_extraction_skipped_using_deterministic", error=str(exc))

        # Prepare content JSONB
        content_payload = extracted.model_dump(mode="json")

        # Create Profile Version
        profile_version = await self.profile_repo.create_profile_version(
            user_id=uid,
            resume_version_id=resume_version_id,
            content=content_payload,
            skills=extracted.skills,
            target_roles=extracted.target_roles,
            seniority_level=extracted.seniority_level,
            years_experience=float(extracted.years_experience)
            if extracted.years_experience
            else None,
        )
        pvid = str(profile_version["id"])

        # Persist Provenance Evidence Claims
        evidence_tasks = []

        # Skills evidence
        for skill in extracted.skills[:30]:  # limit top skills for evidence tracking
            excerpt, conf = self.find_evidence_source_text(raw_text, skill)
            evidence_tasks.append(
                (
                    "skill",
                    skill,
                    conf,
                    excerpt,
                )
            )

        # Employment history evidence
        for emp in extracted.employment_history:
            excerpt, conf = self.find_evidence_source_text(raw_text, emp.company)
            evidence_tasks.append(
                (
                    "employer",
                    f"{emp.title} at {emp.company}",
                    conf,
                    excerpt,
                )
            )

        # Education evidence
        for edu in extracted.education:
            excerpt, conf = self.find_evidence_source_text(raw_text, edu.institution)
            evidence_tasks.append(
                (
                    "education",
                    f"{edu.degree} - {edu.institution}",
                    conf,
                    excerpt,
                )
            )

        # Save evidence rows
        for claim_type, claim_value, conf, excerpt in evidence_tasks:
            try:
                await self.profile_repo.add_profile_evidence(
                    user_id=uid,
                    profile_version_id=pvid,
                    claim_type=claim_type,
                    claim_value=claim_value,
                    confidence=conf,
                    source_text=excerpt,
                )
            except Exception as e:
                log.warning("failed_to_save_evidence", user_id=uid, claim=claim_value, error=str(e))

        # Update candidate user profile contact info from extraction
        try:
            update_fields: dict[str, Any] = {}
            if extracted.contact.name:
                update_fields["display_name"] = extracted.contact.name
            if extracted.contact.email:
                update_fields["contact_email"] = extracted.contact.email
            if extracted.contact.phone:
                update_fields["contact_phone"] = extracted.contact.phone
            if extracted.contact.location:
                update_fields["location"] = extracted.contact.location
            if extracted.contact.linkedin_url:
                update_fields["linkedin_url"] = extracted.contact.linkedin_url
            if extracted.contact.portfolio_url:
                update_fields["portfolio_url"] = extracted.contact.portfolio_url

            if update_fields:
                await self.profile_repo.upsert_profile(uid, update_fields)
        except Exception as err:
            log.warning("profile_metadata_sync_failed", user_id=uid, error=str(err))

        log.info(
            "profile_extracted_successfully",
            user_id=uid,
            profile_version_id=pvid,
            skills_count=len(extracted.skills),
        )
        return profile_version
