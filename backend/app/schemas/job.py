"""
Pydantic contracts and models for job discovery, normalization, and search runs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CanonicalJob(BaseModel):
    """
    Provider-agnostic normalized representation of a discovered job.
    """

    source_name: str = Field(description="Name of the job provider (e.g. remotive, arbeitnow)")
    source_job_id: str = Field(description="Provider-specific unique job identifier")
    canonical_url: str = Field(description="Direct URL to view or apply for the job")
    title: str = Field(description="Clean normalized job title")
    employer: str = Field(description="Hiring company or organization name")
    location: str | None = Field(default=None, description="Location text or region requirement")
    work_arrangement: Literal["remote", "hybrid", "onsite"] | None = Field(
        default=None, description="Remote work categorization"
    )
    employment_type: Literal["full_time", "part_time", "contract", "internship"] | None = Field(
        default=None, description="Employment type"
    )
    seniority: str | None = Field(default=None, description="Seniority level if available")
    description: str = Field(description="Sanitized plain text description of the job")
    salary_min: int | None = Field(default=None, description="Minimum salary if specified")
    salary_max: int | None = Field(default=None, description="Maximum salary if specified")
    salary_currency: str | None = Field(default=None, description="Currency code (e.g. USD, EUR)")
    published_at: datetime | None = Field(
        default=None, description="Original publication timestamp"
    )
    attribution: str = Field(description="Attribution text or link per provider ToS")


class JobResponse(BaseModel):
    """API representation of a persisted job listing."""

    id: UUID
    source_name: str
    source_job_id: str
    canonical_url: str
    title: str
    employer: str
    location: str | None = None
    work_arrangement: str | None = None
    employment_type: str | None = None
    seniority: str | None = None
    description: str
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime
    is_expired: bool = False
    attribution: str


class JobSearchRequest(BaseModel):
    """Payload to trigger an on-demand job discovery run via LinkedIn Apify scraper."""

    query: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
        description="Search keywords, role titles, or core skills (e.g., 'Machine Learning Engineer')",
    )
    urls: list[str] | None = Field(
        default=None,
        description="Optional list of direct LinkedIn search URLs",
    )
    remote_only: bool = Field(default=False, description="Filter for remote jobs only")
    location: str | None = Field(default=None, description="Target city, region, or country (e.g. 'Cairo, Egypt', 'London')")
    geo_id: str | None = Field(default=None, description="Optional LinkedIn geoId for precise location targeting")
    distance: int | None = Field(default=None, description="Search radius in miles around the location")
    date_posted: Literal["past24Hours", "pastWeek", "pastMonth", "anyTime"] | None = Field(
        default="anyTime", description="LinkedIn publication time filter"
    )
    company_ids: list[str] | None = Field(default=None, description="LinkedIn numeric company IDs")
    under_10_applicants: bool = Field(
        default=False, description="Filter for postings with fewer than 10 applicants"
    )
    auto_convert_to_ai_search: bool = Field(default=True, description="Enable AI search filter conversion")
    scrape_company: bool = Field(default=True, description="Scrape company details")
    limit_per_provider: int = Field(
        default=35,
        ge=1,
        le=100,
        description="Maximum jobs to fetch from LinkedIn scraper (up to 100)",
    )
    split_by_location: bool = Field(default=False, description="Split search by cities within country")
    split_country: str | None = Field(default=None, description="Country code to split search by")


class SearchRunResponse(BaseModel):
    """Record of an automated or manual job discovery search execution."""

    id: UUID
    user_id: UUID
    profile_version_id: UUID | None = None
    preferences_snapshot: dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    providers_used: list[str] = Field(default_factory=list)
    jobs_found: int | None = None
    matches_created: int | None = None
    error_summary: str | None = None
    retry_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class JobSearchResponse(BaseModel):
    """Response returned upon completing a job discovery search."""

    search_run_id: UUID
    jobs_count: int
    cached: bool
    jobs: list[JobResponse]


class JobAIEvaluation(BaseModel):
    """Detailed LLM validation and fit evaluation of a job against candidate background."""

    job_id: str = Field(description="UUID of evaluated job listing")
    is_valid_match: bool = Field(
        description="Whether this job is a realistic match for candidate experience and preferences"
    )
    fit_level: Literal["Strong Fit", "Potential Fit", "Not a Fit"] = Field(
        description="Fit category determined by AI"
    )
    ai_score: int = Field(ge=0, le=100, description="Overall match score from 0 to 100")
    experience_fit_analysis: str = Field(
        description="Recruiter analysis of candidate's verified experience vs job requirements"
    )
    preference_fit_analysis: str = Field(
        description="Analysis of alignment with candidate location and work arrangement"
    )
    recruiter_rationale: str = Field(
        description="Concise 1-2 sentence overall recommendation or disqualification reason"
    )


class JobAIEvaluationBatch(BaseModel):
    """Collection of structured AI job evaluations."""

    evaluations: list[JobAIEvaluation] = Field(default_factory=list)


class JobAIFilterRequest(BaseModel):
    """Parameters for running AI-powered job search and Gemini filtering."""

    query: str | None = Field(
        default=None,
        description="Optional custom query; defaults to candidate target roles and experience",
    )
    location: str | None = Field(
        default=None,
        description="Target location or region (e.g., 'Remote', 'Cairo, Egypt', 'Worldwide')",
    )
    work_arrangement: str | None = Field(
        default=None,
        description="Work arrangement filter: 'Remote', 'Hybrid', 'On-site', or 'Any'",
    )
    date_posted: Literal["anyTime", "past24Hours", "pastWeek", "pastMonth"] | None = Field(
        default="anyTime",
        description="Publication freshness filter",
    )
    experience_level: str | None = Field(
        default=None,
        description="Experience level: 'Internship', 'Entry level', 'Associate', 'Mid-Senior level', 'Director', 'Executive', or 'Any'",
    )
    employment_type: str | None = Field(
        default=None,
        description="Employment type: 'Full-time', 'Part-time', 'Contract', 'Temporary', 'Internship', or 'Any'",
    )
    min_fit: Literal["all", "valid_only", "strong_only"] = Field(
        default="valid_only",
        description="Filter threshold: 'all', 'valid_only' (Strong + Potential), or 'strong_only'",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum job listings to evaluate and return",
    )



class JobAIFilteredItem(BaseModel):
    """Pairing of a canonical catalog job with its Gemini AI evaluation."""

    job: JobResponse
    evaluation: JobAIEvaluation


class JobAIFilterResponse(BaseModel):
    """Result payload from Gemini AI job discovery and filtering."""

    candidate_summary: dict[str, Any]
    total_evaluated: int
    valid_count: int
    results: list[JobAIFilteredItem]
    search_run_id: UUID | None = None
    query: str | None = None

