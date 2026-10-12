"""
Pydantic contracts and schemas for candidate profiles, extracted data, and preferences.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

# ── Extracted Profile Structure ───────────────────────────────────────────────


class ContactInfo(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    github_url: str | None = None
    links: list[str] = Field(default_factory=list)


class EmploymentEntry(BaseModel):
    company: str
    title: str
    location: str | None = None
    start_date: str | None = None  # e.g. "2021-06" or "June 2021"
    end_date: str | None = None  # e.g. "2023-08" or "Present"
    is_current: bool = False
    description: str | None = None
    achievements: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    institution: str
    degree: str
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    gpa: str | None = None


class CertificationEntry(BaseModel):
    name: str
    issuer: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    credential_id: str | None = None


class ProjectEntry(BaseModel):
    name: str
    description: str | None = None
    url: str | None = None
    technologies: list[str] = Field(default_factory=list)


class ExtractedProfile(BaseModel):
    """
    Structured candidate profile extracted from resume text.
    Validated schema for LLM extraction output.
    """

    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    employment_history: list[EmploymentEntry] = Field(default_factory=list)
    leadership: list[EmploymentEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[CertificationEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    seniority_level: Literal["junior", "mid", "senior", "lead", "executive", "unknown"] = "unknown"
    years_experience: float | None = None


# ── API Request & Response Schemas ───────────────────────────────────────────


class UserProfileUpdate(BaseModel):
    display_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    linkedin: str | None = None
    portfolio_url: str | None = None
    github_url: str | None = None
    years_experience: float | None = None


class UserProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    display_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    github_url: str | None = None
    years_experience: float | None = None
    created_at: datetime
    updated_at: datetime


class ProfileEvidenceItem(BaseModel):
    id: UUID
    claim_type: str
    claim_value: str
    confidence: Literal["explicit", "confirmed", "inferred", "uncertain"]
    source_text: str | None = None
    source_location: str | None = None
    created_at: datetime


class ProfileVersionDetail(BaseModel):
    id: UUID
    version_number: int
    is_confirmed: bool
    content: dict[str, Any]
    skills: list[str]
    target_roles: list[str]
    seniority_level: str | None = None
    years_experience: Decimal | float | None = None
    created_at: datetime
    evidence: list[ProfileEvidenceItem] = Field(default_factory=list)


class SearchPreferencesPayload(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    work_arrangements: list[str] = Field(default_factory=list)
    seniority_levels: list[str] = Field(default_factory=list)
    min_salary: int | None = None
    salary_currency: str = "USD"
    excluded_employers: list[str] = Field(default_factory=list)
    keywords_include: list[str] = Field(default_factory=list)
    keywords_exclude: list[str] = Field(default_factory=list)
    years_experience: float | None = None


class SearchPreferencesResponse(SearchPreferencesPayload):
    id: UUID
    user_id: UUID
    updated_at: datetime
