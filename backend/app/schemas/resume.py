"""
Pydantic contracts and schemas for resume uploads and versions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ResumePasteRequest(BaseModel):
    """Payload for pasting raw resume text."""

    text: str = Field(
        min_length=30,
        max_length=100000,
        description="Raw resume text (minimum 30 characters).",
    )


class ResumeVersionResponse(BaseModel):
    """Resume version record."""

    id: UUID
    user_id: UUID
    version_number: int
    source_type: Literal["pdf", "docx", "text"]
    storage_path: str | None = None
    raw_text: str | None = None
    file_size_bytes: int | None = None
    original_filename: str | None = None
    extraction_status: Literal["pending", "processing", "completed", "failed"]
    extraction_error: str | None = None
    created_at: datetime


class ResumeUploadResponse(BaseModel):
    """Response after uploading or pasting a resume."""

    resume_version_id: UUID
    version_number: int
    source_type: str
    status: str = "pending"
    message: str = "Resume ingested successfully. Extraction task started."
