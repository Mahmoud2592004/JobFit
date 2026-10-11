"""
Resumes API endpoints.

Endpoints:
- POST /api/v1/resumes/upload (multipart PDF/DOCX)
- POST /api/v1/resumes/paste (raw text)
- GET /api/v1/resumes (list versions)
- GET /api/v1/resumes/{id} (get version detail + signed URL)
"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.dependencies import CurrentUser
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.providers.llm import get_llm_adapter
from app.providers.storage.supabase_storage import SupabaseStorageProvider
from app.repositories.profile_repository import ProfileRepository
from app.schemas.resume import (
    ResumePasteRequest,
    ResumeUploadResponse,
    ResumeVersionResponse,
)
from app.services.profile_extraction_service import ProfileExtractionService
from app.services.resume_parser import ResumeParserService

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/resumes", tags=["resumes"])


def get_profile_repo() -> ProfileRepository:
    return ProfileRepository()


def get_storage_provider() -> SupabaseStorageProvider:
    return SupabaseStorageProvider()


def get_parser_service() -> ResumeParserService:
    return ResumeParserService()


def get_extraction_service(
    repo: ProfileRepository = Depends(get_profile_repo),
) -> ProfileExtractionService:
    return ProfileExtractionService(llm=get_llm_adapter(), profile_repo=repo)


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload resume document",
    description=(
        "Upload a PDF or DOCX resume. Validates magic bytes, uploads to private storage, "
        "and extracts text."
    ),
)
async def upload_resume(
    current_user: CurrentUser,
    file: UploadFile = File(...),
    parser: ResumeParserService = Depends(get_parser_service),
    repo: ProfileRepository = Depends(get_profile_repo),
    storage: SupabaseStorageProvider = Depends(get_storage_provider),
    extraction_svc: ProfileExtractionService = Depends(get_extraction_service),
) -> ResumeUploadResponse:
    filename = file.filename or "resume.pdf"
    content = await file.read()

    # 1. Validate and parse file
    source_type, raw_text = parser.parse_file(filename, content)

    # 2. Upload to private Supabase storage
    settings = get_settings()
    unique_name = f"{uuid.uuid4()}_{filename}"
    storage_path = SupabaseStorageProvider.build_user_scoped_path(current_user, unique_name)
    content_type = file.content_type or "application/octet-stream"

    try:
        await storage.upload_file(
            bucket=settings.storage_resume_bucket,
            path=storage_path,
            content=content,
            content_type=content_type,
        )
    except Exception as exc:
        log.warning("storage_upload_warning", error=str(exc))
        # Non-fatal if storage fails during dev; raw text is still persisted

    # 3. Create resume_versions record
    resume_ver = await repo.create_resume_version(
        user_id=current_user,
        source_type=source_type,
        storage_path=storage_path,
        raw_text=raw_text,
        file_size_bytes=len(content),
        original_filename=filename,
    )
    rv_id = resume_ver["id"]

    # 4. Extract structured profile
    try:
        await extraction_svc.extract_and_persist_profile(
            user_id=current_user,
            raw_text=raw_text,
            resume_version_id=rv_id,
        )
        await repo.update_resume_extraction(current_user, rv_id, status="completed")
    except Exception as err:
        log.error("extraction_failed_async", error=str(err))
        await repo.update_resume_extraction(current_user, rv_id, status="failed", error=str(err))

    return ResumeUploadResponse(
        resume_version_id=rv_id,
        version_number=resume_ver["version_number"],
        source_type=source_type,
        status="completed",
        message="Resume uploaded and profile extracted successfully.",
    )


@router.post(
    "/paste",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Paste resume text",
    description="Paste raw resume text directly without uploading a binary file.",
)
async def paste_resume(
    payload: ResumePasteRequest,
    current_user: CurrentUser,
    parser: ResumeParserService = Depends(get_parser_service),
    repo: ProfileRepository = Depends(get_profile_repo),
    extraction_svc: ProfileExtractionService = Depends(get_extraction_service),
) -> ResumeUploadResponse:
    cleaned = parser.clean_text(payload.text)

    # Create resume version with source_type='text'
    resume_ver = await repo.create_resume_version(
        user_id=current_user,
        source_type="text",
        storage_path=None,
        raw_text=cleaned,
        file_size_bytes=len(cleaned.encode("utf-8")),
        original_filename=None,
    )
    rv_id = resume_ver["id"]

    # Extract structured profile
    try:
        await extraction_svc.extract_and_persist_profile(
            user_id=current_user,
            raw_text=cleaned,
            resume_version_id=rv_id,
        )
        await repo.update_resume_extraction(current_user, rv_id, status="completed")
    except Exception as err:
        log.error("paste_extraction_failed", error=str(err))
        await repo.update_resume_extraction(current_user, rv_id, status="failed", error=str(err))

    return ResumeUploadResponse(
        resume_version_id=rv_id,
        version_number=resume_ver["version_number"],
        source_type="text",
        status="completed",
        message="Resume text saved and profile extracted successfully.",
    )


@router.get(
    "",
    response_model=list[ResumeVersionResponse],
    summary="List resume versions",
    description="Retrieve all uploaded or pasted resume versions for the current user.",
)
async def list_resume_versions(
    current_user: CurrentUser,
    repo: ProfileRepository = Depends(get_profile_repo),
) -> list[dict[str, Any]]:
    return await repo.get_resume_versions(current_user)


@router.get(
    "/{version_id}",
    response_model=ResumeVersionResponse,
    summary="Get resume version detail",
    description="Retrieve specific resume version details for the authenticated user.",
)
async def get_resume_version(
    version_id: UUID,
    current_user: CurrentUser,
    repo: ProfileRepository = Depends(get_profile_repo),
) -> dict[str, Any]:
    version = await repo.get_resume_version(current_user, version_id)
    if not version:
        raise NotFoundError("Resume version")
    return version
