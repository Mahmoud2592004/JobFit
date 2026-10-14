"""
Resume Tailoring Engine.
Orchestrates AI-driven resume tailoring, strict anti-hallucination claim verification,
document rendering, and user-isolated private storage uploads.
"""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import UUID

import structlog

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.providers.llm.base import LLMAdapter
from app.providers.storage.base import StorageProvider
from app.repositories.job_repository import JobRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.tailored_document_repository import TailoredDocumentRepository
from app.schemas.tailoring import (
    TailoredResumeContent,
)
from app.services.claim_verifier import VALIDATION_VERSION, ClaimVerifier
from app.services.document_renderer import DocumentRenderer

log = structlog.get_logger(__name__)

_TAILORING_SYSTEM_PROMPT = """
You are an expert executive resume tailoring strategist with strict factual rigor.
Your mission is to tailor a candidate's resume specifically for a target job listing
in an ATS-friendly, high-impact format.

CORE DIRECTIVE - ACTIVE TAILORING & REWRITING:
You MUST actively rewrite and customize the bullet points for work experience and projects
to directly align with the qualifications, technical keywords, and responsibilities demanded
by the target job listing. Do NOT merely copy existing bullet points or descriptions verbatim.

TAILORING RULES & RIGOROUS FACTUAL BOUNDARIES:
1. FACTUAL GROUNDING: Anchor every claim in the candidate's actual profile facts.
   - ONLY utilize employers, job titles, dates, degrees, projects, and skills present in candidate profile data.
   - DO NOT fabricate employers, job titles, unearned degrees, or unmentioned technologies.
   - Keep factual metrics, team sizes, and genuine achievements grounded in the profile facts.
2. EXPERIENCE BULLET TAILORING:
   - Include ALL employment history entries from the candidate profile with exact company names, dates, and titles.
   - For each role, produce 2 to 4 crisp, high-impact bullet points.
   - Actively rephrase each bullet point using strong action verbs (e.g., "Architected", "Engineered", "Streamlined", "Spearheaded") that highlight how the candidate's past work directly relates to the target job's tech stack and requirements.
   - Elevate the most relevant achievements to the top of each role.
3. PROJECTS TAILORING:
   - For each relevant project, generate 1 to 3 tailored bullet points detailing the problem solved, technologies utilized, and quantifiable impact, customized to emphasize relevance to the target job.
4. EDUCATION & COURSEWORK:
   - Preserve degree, institution, and graduation dates.
   - If relevant to the target job requirements, include matching coursework in the coursework field.
5. SKILLS CURATION:
   - Prioritize and lead with candidate skills that directly map to the target job qualifications.
6. TONE & STYLE:
   - Professional, concise, action-verb driven, ATS-optimized, with no fluff or filler phrases.
"""


class TailoringService:
    """Service orchestrating AI resume tailoring, claim verification, and PDF generation."""

    def __init__(
        self,
        llm: LLMAdapter,
        tailored_repo: TailoredDocumentRepository,
        profile_repo: ProfileRepository,
        job_repo: JobRepository,
        storage: StorageProvider,
    ) -> None:
        self.llm = llm
        self.tailored_repo = tailored_repo
        self.profile_repo = profile_repo
        self.job_repo = job_repo
        self.storage = storage
        self.settings = get_settings()

    async def generate_tailored_content(
        self,
        job: dict[str, Any],
        profile_data: dict[str, Any],
        target_role_notes: str | None = None,
    ) -> TailoredResumeContent:
        """
        Invoke Gemini directly to tailor headline, summary, skills, experience bullet points,
        and projects for the target job while preserving factual accuracy.
        """
        notes_section = (
            f"Candidate Focus / Role Notes: {target_role_notes}\n\n"
            if target_role_notes
            else ""
        )
        prompt = (
            f"=== TARGET JOB LISTING ===\n"
            f"Title: {job.get('title')}\n"
            f"Company: {job.get('employer') or job.get('company')}\n"
            f"Description:\n{job.get('description') or ''}\n\n"
            f"{notes_section}"
            f"=== CANDIDATE PROFILE ===\n"
            f"{json.dumps(profile_data, indent=2)}\n\n"
            f"=== OBJECTIVE ===\n"
            f"Tailor the resume for the target job listing above.\n"
            f"1. Generate a compelling target headline and professional summary.\n"
            f"2. Curate and prioritize skills matching the job description.\n"
            f"3. Actively rewrite each employment experience entry with 2-4 tailored, action-oriented bullet points emphasizing relevance to the job requirements while retaining factual integrity.\n"
            f"4. Tailor project descriptions and bullet points to highlight the relevant tech stack and impact.\n"
            f"5. Populate education and relevant coursework.\n"
            f"Return the tailored resume strictly conforming to the JSON schema."
        )

        return await self.llm.extract_structured(
            prompt=prompt,
            response_model=TailoredResumeContent,
            system_instruction=_TAILORING_SYSTEM_PROMPT,
            temperature=0.4,
        )

    async def tailor_resume_for_job(
        self,
        user_id: UUID | str,
        job_id: UUID | str,
        profile_version_id: UUID | str | None = None,
        template_version: str = "modern-clean-v1",
        target_role_notes: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate, verify, render, and persist a tailored resume for a job listing.
        """
        uid = str(user_id)
        jid = str(job_id)

        # 1. Fetch Target Job
        job = await self.job_repo.get_job(jid)
        if not job:
            raise NotFoundError(resource=f"Job listing {jid}")

        # 2. Fetch Profile Version
        if profile_version_id:
            p_ver = await self.profile_repo.get_profile_version(uid, profile_version_id)
        else:
            p_ver = await self.profile_repo.get_active_profile_version(uid)

        if not p_ver:
            raise NotFoundError(resource=f"Candidate profile version for user {uid}")

        pvid = str(p_ver["id"])
        profile_data = p_ver.get("content") or p_ver.get("profile_data") or {}

        # 3. Create initial document record in 'generating' state
        doc = await self.tailored_repo.create_document(
            user_id=uid,
            job_id=jid,
            profile_version_id=pvid,
            template_version=template_version,
            status="generating",
        )
        doc_id = str(doc["id"])

        start_time = time.perf_counter()

        try:
            # 4. Invoke LLM for structured tailoring
            tailored_content = await self.generate_tailored_content(
                job=job,
                profile_data=profile_data,
                target_role_notes=target_role_notes,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # 5. Strict Claim Verification
            validation_passed, flagged_claims = ClaimVerifier.verify_tailored_content(
                tailored=tailored_content,
                verified_profile=profile_data,
            )

            final_status = "approved" if validation_passed else "review_required"

            # 6. Render Document & Upload to Storage
            profile_info = await self.profile_repo.get_profile(uid)
            contact = {**(profile_data.get("contact") or {}), **(profile_info or {})}

            doc_bytes, content_type = DocumentRenderer.render_pdf(tailored_content, contact)
            file_ext = "pdf" if "pdf" in content_type else "html"
            storage_path = f"{uid}/{doc_id}.{file_ext}"

            await self.storage.upload_file(
                bucket=self.settings.storage_documents_bucket,
                path=storage_path,
                content=doc_bytes,
                content_type=content_type,
            )

            # 7. Update Record with Tailored Content and Metrics
            updated_doc = await self.tailored_repo.update_document(
                doc_id=doc_id,
                user_id=uid,
                updates={
                    "status": final_status,
                    "structured_content": tailored_content.model_dump(),
                    "storage_path": storage_path,
                    "flagged_claims": [f.model_dump() for f in flagged_claims],
                    "validation_passed": validation_passed,
                    "validation_version": VALIDATION_VERSION,
                    "model_used": "gemini-3.5-flash-lite",
                    "generation_latency_ms": latency_ms,
                },
            )

            result = updated_doc or doc
            result["download_url"] = await self.storage.create_signed_url(
                bucket=self.settings.storage_documents_bucket,
                path=storage_path,
                expires_in=self.settings.signed_url_expiry_seconds,
            )
            return result

        except Exception as exc:
            log.error("tailoring_pipeline_failed", doc_id=doc_id, user_id=uid, error=str(exc))
            await self.tailored_repo.update_document(
                doc_id=doc_id,
                user_id=uid,
                updates={
                    "status": "failed",
                    "error_summary": str(exc),
                },
            )
            raise

    async def update_tailored_content(
        self,
        user_id: UUID | str,
        doc_id: UUID | str,
        new_content: TailoredResumeContent,
    ) -> dict[str, Any]:
        """
        User modifies tailored resume content, re-verifies claims, and re-renders PDF.
        """
        uid = str(user_id)
        did = str(doc_id)

        doc = await self.tailored_repo.get_document(uid, did)
        if not doc:
            raise NotFoundError(resource=f"Tailored document {did}")

        pvid = str(doc["profile_version_id"])
        p_ver = await self.profile_repo.get_profile_version(uid, pvid)
        profile_data = (p_ver.get("content") or p_ver.get("profile_data") or {}) if p_ver else {}

        # Re-verify claims
        validation_passed, flagged_claims = ClaimVerifier.verify_tailored_content(
            tailored=new_content,
            verified_profile=profile_data,
        )

        final_status = "approved" if validation_passed else "review_required"

        # Re-render and upload
        profile_info = await self.profile_repo.get_profile(uid)
        contact = {**(profile_data.get("contact") or {}), **(profile_info or {})}

        doc_bytes, content_type = DocumentRenderer.render_pdf(new_content, contact)
        file_ext = "pdf" if "pdf" in content_type else "html"
        storage_path = f"tailored_resumes/{uid}/{did}.{file_ext}"

        await self.storage.upload_file(
            bucket=self.settings.storage_documents_bucket,
            path=storage_path,
            content=doc_bytes,
            content_type=content_type,
        )

        updated = await self.tailored_repo.update_document(
            doc_id=did,
            user_id=uid,
            updates={
                "status": final_status,
                "structured_content": new_content.model_dump(),
                "storage_path": storage_path,
                "flagged_claims": [f.model_dump() for f in flagged_claims],
                "validation_passed": validation_passed,
            },
        )

        res = updated or doc
        res["download_url"] = await self.storage.create_signed_url(
            bucket=self.settings.storage_documents_bucket,
            path=storage_path,
            expires_in=self.settings.signed_url_expiry_seconds,
        )
        return res

    async def approve_document(
        self,
        user_id: UUID | str,
        doc_id: UUID | str,
    ) -> dict[str, Any]:
        """Candidate explicitly confirms and approves tailored document."""
        uid = str(user_id)
        did = str(doc_id)

        doc = await self.tailored_repo.get_document(uid, did)
        if not doc:
            raise NotFoundError(resource=f"Tailored document {did}")

        updated = await self.tailored_repo.update_document(
            doc_id=did,
            user_id=uid,
            updates={
                "status": "approved",
                "validation_passed": True,
            },
        )
        res = updated or doc
        if path := res.get("storage_path"):
            res["download_url"] = await self.storage.create_signed_url(
                bucket=self.settings.storage_documents_bucket,
                path=path,
                expires_in=self.settings.signed_url_expiry_seconds,
            )
        return res

    async def get_document_with_url(
        self,
        user_id: UUID | str,
        doc_id: UUID | str,
    ) -> dict[str, Any]:
        """Fetch tailored document and append signed storage download URL."""
        uid = str(user_id)
        did = str(doc_id)

        doc = await self.tailored_repo.get_document(uid, did)
        if not doc:
            raise NotFoundError(resource=f"Tailored document {did}")

        if path := doc.get("storage_path"):
            doc["download_url"] = await self.storage.create_signed_url(
                bucket=self.settings.storage_documents_bucket,
                path=path,
                expires_in=self.settings.signed_url_expiry_seconds,
            )
        return doc
