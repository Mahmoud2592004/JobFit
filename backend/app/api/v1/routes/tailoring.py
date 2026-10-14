"""
API endpoints for resume tailoring, claim review, and document downloads.
"""

from __future__ import annotations

import re
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_current_user
from app.api.v1.routes.jobs import get_job_repository
from app.api.v1.routes.profile import get_profile_repo
from app.api.v1.routes.resumes import get_llm_adapter, get_storage_provider
from app.providers.llm.base import LLMAdapter
from app.providers.storage.base import StorageProvider
from app.repositories.job_repository import JobRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.tailored_document_repository import TailoredDocumentRepository
from app.schemas.tailoring import (
    CoverLetterContent,
    CoverLetterPreviewRequest,
    TailoredDocumentResponse,
    TailoredResumeContent,
    TailorPreviewRequest,
    TailorResumeRequest,
    UpdateTailoredContentRequest,
)
from app.services.cover_letter_service import CoverLetterService
from app.services.tailoring_service import TailoringService

router = APIRouter(prefix="/tailored-documents", tags=["Tailored Resumes"])
tailor_action_router = APIRouter(prefix="/tailor", tags=["Tailored Resumes"])


def get_tailored_doc_repo() -> TailoredDocumentRepository:
    """Dependency factory for TailoredDocumentRepository."""
    return TailoredDocumentRepository()


def get_tailoring_service(
    llm: Annotated[LLMAdapter, Depends(get_llm_adapter)],
    tailored_repo: Annotated[TailoredDocumentRepository, Depends(get_tailored_doc_repo)],
    profile_repo: Annotated[ProfileRepository, Depends(get_profile_repo)],
    job_repo: Annotated[JobRepository, Depends(get_job_repository)],
    storage: Annotated[StorageProvider, Depends(get_storage_provider)],
) -> TailoringService:
    """Dependency factory for TailoringService."""
    return TailoringService(
        llm=llm,
        tailored_repo=tailored_repo,
        profile_repo=profile_repo,
        job_repo=job_repo,
        storage=storage,
    )


def get_cover_letter_service(
    llm: Annotated[LLMAdapter, Depends(get_llm_adapter)],
) -> CoverLetterService:
    """Dependency factory for CoverLetterService."""
    return CoverLetterService(llm=llm)


@tailor_action_router.post(
    "/preview",
    response_model=TailoredResumeContent,
    status_code=status.HTTP_200_OK,
    summary="Generate tailored resume content with Gemini",
)
async def preview_tailored_resume(
    payload: TailorPreviewRequest,
    service: Annotated[TailoringService, Depends(get_tailoring_service)],
) -> TailoredResumeContent:
    """
    Generate structured tailored resume with rewritten bullet points via Gemini
    directly from target job and candidate profile facts.
    """
    return await service.generate_tailored_content(
        job=payload.job,
        profile_data=payload.candidate_profile,
        target_role_notes=payload.target_role_notes,
    )


@tailor_action_router.post(
    "/cover-letter/preview",
    response_model=CoverLetterContent,
    status_code=status.HTTP_200_OK,
    summary="Generate tailored personalized cover letter with Gemini",
)
async def preview_cover_letter(
    payload: CoverLetterPreviewRequest,
    service: Annotated[CoverLetterService, Depends(get_cover_letter_service)],
) -> CoverLetterContent:
    """
    Generate an authentic, deeply personalized, natural cover letter using Gemini,
    with prompt instructions to search/research first about the company.
    """
    return await service.generate_cover_letter(
        job=payload.job,
        candidate_profile=payload.candidate_profile,
        target_role_notes=payload.target_role_notes,
        tone=payload.tone,
    )



@tailor_action_router.post(
    "",
    response_model=TailoredDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate tailored resume for target job",
)
async def tailor_resume(
    payload: TailorResumeRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[TailoringService, Depends(get_tailoring_service)],
) -> TailoredDocumentResponse:
    """
    Generate an AI-tailored resume specifically aligned with the target job,
    verify all claims against candidate source facts, render to PDF,
    and persist in the user's private storage.
    """
    doc = await service.tailor_resume_for_job(
        user_id=user_id,
        job_id=payload.job_id,
        profile_version_id=payload.profile_version_id,
        template_version=payload.template_version,
        target_role_notes=payload.target_role_notes,
    )
    return TailoredDocumentResponse.model_validate(doc)


@router.get(
    "",
    response_model=list[TailoredDocumentResponse],
    summary="List tailored documents for current user",
)
async def list_tailored_documents(
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[TailoredDocumentRepository, Depends(get_tailored_doc_repo)],
    job_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[TailoredDocumentResponse]:
    """List historical tailored documents for user, optionally filtered by job."""
    records = await repo.list_documents(user_id=user_id, job_id=job_id, limit=limit)
    return [TailoredDocumentResponse.model_validate(r) for r in records]


@router.get(
    "/{document_id}",
    response_model=TailoredDocumentResponse,
    summary="Get tailored document details with signed download URL",
)
async def get_tailored_document(
    document_id: UUID,
    user_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[TailoringService, Depends(get_tailoring_service)],
) -> TailoredDocumentResponse:
    """Retrieve structured content, validation audit, and signed download URL."""
    doc = await service.get_document_with_url(user_id=user_id, doc_id=document_id)
    return TailoredDocumentResponse.model_validate(doc)


@router.put(
    "/{document_id}",
    response_model=TailoredDocumentResponse,
    summary="Update tailored resume content and re-verify claims",
)
async def update_tailored_document(
    document_id: UUID,
    payload: UpdateTailoredContentRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[TailoringService, Depends(get_tailoring_service)],
) -> TailoredDocumentResponse:
    """Edit structured sections; automatically re-verifies claims against facts."""
    doc = await service.update_tailored_content(
        user_id=user_id,
        doc_id=document_id,
        new_content=payload.structured_content,
    )
    return TailoredDocumentResponse.model_validate(doc)


@router.post(
    "/{document_id}/approve",
    response_model=TailoredDocumentResponse,
    summary="Explicitly approve tailored document for use",
)
async def approve_tailored_document(
    document_id: UUID,
    user_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[TailoringService, Depends(get_tailoring_service)],
) -> TailoredDocumentResponse:
    """Mark a tailored document as approved, clearing review_required state."""
    doc = await service.approve_document(user_id=user_id, doc_id=document_id)
    return TailoredDocumentResponse.model_validate(doc)


@router.get(
    "/{document_id}/download",
    summary="Get download URL and formatted filename for tailored resume",
)
async def get_document_download_url(
    document_id: UUID,
    user_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[TailoringService, Depends(get_tailoring_service)],
) -> dict[str, Any]:
    """Retrieve signed download URL and ATS-standard file name."""
    doc = await service.get_document_with_url(user_id=user_id, doc_id=document_id)
    download_url = doc.get("download_url") or ""

    # Extract candidate name
    content = doc.get("structured_content") or {}
    contact = content.get("contact") or doc.get("contact_info") or {}
    user_name = contact.get("name") or "Candidate"

    # Fetch job info
    job_title = "Tailored Resume"
    employer = "Role"
    if jid := doc.get("job_id"):
        job = await service.job_repo.get_job(jid)
        if job:
            job_title = job.get("title") or job_title
            employer = job.get("employer") or employer

    # Construct standard filename: UserName - Role - Company.pdf
    clean_title = re.sub(r'[\/:*?"<>|]', '', job_title).strip()
    clean_employer = re.sub(r'[\/:*?"<>|]', '', employer).strip()
    clean_user = re.sub(r'[\/:*?"<>|]', '', user_name).strip()
    filename = f"{clean_user} - {clean_title} - {clean_employer}.pdf"

    return {
        "download_url": download_url,
        "filename": filename,
        "expires_in_seconds": service.settings.signed_url_expiry_seconds,
    }

