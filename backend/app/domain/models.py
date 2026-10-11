"""
Internal domain models for JobFit backend.

These Pydantic models represent business entities stored in PostgreSQL/Supabase.
All user-owned models have an explicit user_id field.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """User profile entity (1:1 with auth.users)."""

    id: UUID
    user_id: UUID
    display_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    created_at: datetime
    updated_at: datetime


class ResumeVersion(BaseModel):
    """Uploaded or pasted resume record."""

    id: UUID
    user_id: UUID
    version_number: int
    source_type: Literal["pdf", "docx", "text"]
    storage_path: str | None = None
    raw_text: str | None = None
    file_size_bytes: int | None = None
    original_filename: str | None = None
    extraction_status: Literal["pending", "processing", "completed", "failed"] = "pending"
    extraction_error: str | None = None
    created_at: datetime


class ProfileVersion(BaseModel):
    """Structured, versioned profile extracted or edited from a resume."""

    id: UUID
    user_id: UUID
    resume_version_id: UUID | None = None
    version_number: int
    is_confirmed: bool = False
    content: dict[str, Any] = Field(default_factory=dict)
    seniority_level: str | None = None
    target_roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    years_experience: Decimal | None = None
    created_at: datetime


class ProfileEvidence(BaseModel):
    """Provenance tracking connecting a resume claim to its source text."""

    id: UUID
    profile_version_id: UUID
    user_id: UUID
    claim_type: str
    claim_value: str
    confidence: Literal["explicit", "confirmed", "inferred", "uncertain"]
    source_text: str | None = None
    source_location: str | None = None
    created_at: datetime


class SearchPreferences(BaseModel):
    """Candidate job search settings."""

    id: UUID
    user_id: UUID
    target_roles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    work_arrangements: list[str] = Field(default_factory=list)
    seniority_levels: list[str] = Field(default_factory=list)
    min_salary: int | None = None
    salary_currency: str = "USD"
    excluded_employers: list[str] = Field(default_factory=list)
    keywords_include: list[str] = Field(default_factory=list)
    keywords_exclude: list[str] = Field(default_factory=list)
    updated_at: datetime


class Task(BaseModel):
    """Asynchronous background task entity."""

    id: UUID
    user_id: UUID
    task_type: str
    reference_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending"
    retry_count: int = 0
    max_retries: int = 3
    error_message: str | None = None
    result: dict[str, Any] | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    claimed_by: str | None = None
    claimed_at: datetime | None = None
