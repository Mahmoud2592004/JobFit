"""
Pydantic contracts and schemas for job matching, score breakdowns, and explainability.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.job import JobResponse


class ScoreBreakdown(BaseModel):
    """Detailed breakdown of match scoring components."""

    skills_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Technical and professional skill overlap score (0-100)",
    )
    experience_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Seniority level and years of experience match score (0-100)",
    )
    role_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Role title and target specialization alignment score (0-100)",
    )
    work_arrangement_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Remote / hybrid / location compatibility score (0-100)",
    )


class JobMatchResponse(BaseModel):
    """Evaluated match record between a candidate profile and a job listing."""

    id: UUID
    user_id: UUID
    job_id: UUID
    search_run_id: UUID | None = None
    profile_version_id: UUID | None = None
    overall_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Deterministic overall compatibility score (0-100)",
    )
    scoring_version: str = Field(description="Algorithm version (e.g. 'v1.0.0')")
    score_breakdown: ScoreBreakdown
    matching_evidence: list[str] = Field(
        default_factory=list,
        description="Evidence-backed reasons why candidate is a strong fit",
    )
    missing_requirements: list[str] = Field(
        default_factory=list,
        description="Job requirements or skills not detected in candidate profile",
    )
    uncertain_factors: list[str] = Field(
        default_factory=list,
        description="Ambiguous or unconfirmed eligibility factors",
    )
    freshness_warning: str | None = Field(
        default=None,
        description="Warning notice if job is stale or expired",
    )
    evaluated_at: datetime
    is_saved: bool = False
    saved_at: datetime | None = None
    job: JobResponse | None = None


class BatchMatchRequest(BaseModel):
    """Request payload to evaluate matches for multiple jobs."""

    job_ids: list[UUID] = Field(
        min_length=1,
        max_length=50,
        description="List of job UUIDs to evaluate against active profile",
    )
    search_run_id: UUID | None = Field(
        default=None,
        description="Optional search run identifier to associate with matches",
    )


class BatchMatchResponse(BaseModel):
    """Response returned upon batch matching evaluation."""

    evaluated_count: int
    matches: list[JobMatchResponse]
