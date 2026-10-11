"""
Pydantic contracts and schemas for resume tailoring, claim verification, and document rendering.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class FlaggedClaim(BaseModel):
    """An uncorroborated or potentially exaggerated claim requiring user review."""

    claim: str = Field(description="The specific generated text or claim")
    field_path: str = Field(description="JSON path or section where claim occurred")
    reason: str = Field(description="Explanation of why this claim could not be verified")
    severity: Literal["warning", "error"] = Field(
        default="warning",
        description="Severity ('warning' for unconfirmed nuances, 'error' for invented facts)",
    )


class TailoredExperienceEntry(BaseModel):
    """Experience entry in tailored resume."""

    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = None
    location: str | None = None
    bullet_points: list[str] = Field(default_factory=list)


class TailoredResumeContent(BaseModel):
    """Structured tailored resume content produced by AI model."""

    headline: str = Field(description="Job-targeted professional title / headline")
    summary: str = Field(description="Job-tailored professional summary")
    skills: list[str] = Field(
        default_factory=list,
        description="Prioritized skills strictly derived from verified profile",
    )
    experience: list[TailoredExperienceEntry] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)


class TailorResumeRequest(BaseModel):
    """Request payload to generate a tailored resume for a target job."""

    job_id: UUID = Field(description="Target job listing UUID")
    profile_version_id: UUID | None = Field(
        default=None,
        description="Optional profile version ID; if omitted, uses active profile",
    )
    template_version: str = Field(
        default="modern-clean-v1",
        description="Resume visual template identifier",
    )
    target_role_notes: str | None = Field(
        default=None,
        description="Optional candidate notes or target role focus",
    )


class UpdateTailoredContentRequest(BaseModel):
    """Payload for user edits to structured tailored resume content."""

    structured_content: TailoredResumeContent


class TailoredDocumentResponse(BaseModel):
    """API representation of a tailored document record."""

    id: UUID
    user_id: UUID
    job_id: UUID
    profile_version_id: UUID
    status: Literal["pending", "generating", "review_required", "approved", "failed"]
    structured_content: TailoredResumeContent | None = None
    storage_path: str | None = None
    download_url: str | None = None
    flagged_claims: list[FlaggedClaim] = Field(default_factory=list)
    validation_passed: bool | None = None
    validation_version: str | None = None
    scoring_version: str | None = None
    template_version: str | None = None
    model_used: str | None = None
    generation_latency_ms: int | None = None
    error_summary: str | None = None
    created_at: datetime
    updated_at: datetime
