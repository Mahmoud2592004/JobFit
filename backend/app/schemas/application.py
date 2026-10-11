"""
Pydantic contracts and schemas for application tracking and timeline events.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.job import JobResponse

ApplicationStatus = Literal[
    "saved",
    "preparing",
    "applied",
    "interviewing",
    "offered",
    "rejected",
    "withdrawn",
    "archived",
]


class CreateApplicationRequest(BaseModel):
    """Payload to create or track an application for a job."""

    job_id: UUID = Field(description="Target job listing UUID")
    tailored_document_id: UUID | None = Field(
        default=None,
        description="Optional tailored resume attached to this application",
    )
    status: ApplicationStatus = Field(
        default="saved",
        description="Initial lifecycle status",
    )
    notes: str | None = Field(default=None, description="Initial private user notes")


class UpdateApplicationRequest(BaseModel):
    """Payload to update an existing application's status, document, or notes."""

    status: ApplicationStatus | None = None
    tailored_document_id: UUID | None = None
    notes: str | None = None
    applied_at: datetime | None = None


class AddApplicationEventRequest(BaseModel):
    """Payload to log a timeline event on an application."""

    event_type: str = Field(
        description="Event type (e.g. status_change, note_added, interview_scheduled)",
    )
    note: str | None = Field(default=None, description="Event description or notes")
    event_data: dict[str, Any] = Field(default_factory=dict, description="Metadata")


class ApplicationEventResponse(BaseModel):
    """Audit log entry in application history timeline."""

    id: UUID
    application_id: UUID
    user_id: UUID
    from_status: str | None = None
    to_status: str
    note: str | None = None
    event_type: str | None = None
    event_data: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime
    created_at: datetime | None = None


class ApplicationResponse(BaseModel):
    """Full application record with embedded job listing details."""

    id: UUID
    user_id: UUID
    job_id: UUID
    tailored_document_id: UUID | None = None
    status: ApplicationStatus
    notes: str | None = None
    applied_at: datetime | None = None
    follow_up_date: datetime | None = None
    offer_amount: int | None = None
    offer_currency: str | None = None
    last_activity_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    job: JobResponse | None = None
