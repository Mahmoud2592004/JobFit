"""
API endpoints for job application tracking and timeline events.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.repositories.application_repository import ApplicationRepository
from app.schemas.application import (
    AddApplicationEventRequest,
    ApplicationEventResponse,
    ApplicationResponse,
    ApplicationStatus,
    CreateApplicationRequest,
    UpdateApplicationRequest,
)

router = APIRouter(prefix="/applications", tags=["Applications"])


def get_application_repo() -> ApplicationRepository:
    """Dependency factory for ApplicationRepository."""
    return ApplicationRepository()


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Track a new job application",
)
async def create_application(
    payload: CreateApplicationRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[ApplicationRepository, Depends(get_application_repo)],
) -> ApplicationResponse:
    """Create a tracked job application in the Kanban pipeline."""
    app_data = await repo.create_application(
        user_id=user_id,
        job_id=payload.job_id,
        tailored_document_id=payload.tailored_document_id,
        status=payload.status,
        notes=payload.notes,
    )
    return ApplicationResponse.model_validate(app_data)


@router.get(
    "",
    response_model=list[ApplicationResponse],
    summary="List tracked job applications",
)
async def list_applications(
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[ApplicationRepository, Depends(get_application_repo)],
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ApplicationResponse]:
    """Retrieve user's job applications with attached job listings."""
    records = await repo.list_applications(
        user_id=user_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [ApplicationResponse.model_validate(r) for r in records]


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Get application details",
)
async def get_application(
    application_id: UUID,
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[ApplicationRepository, Depends(get_application_repo)],
) -> ApplicationResponse:
    """Retrieve full application details by ID."""
    app_data = await repo.get_application(user_id=user_id, application_id=application_id)
    if not app_data:
        raise NotFoundError(resource=f"Application {application_id}")
    return ApplicationResponse.model_validate(app_data)


@router.patch(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Update application status or notes",
)
async def update_application(
    application_id: UUID,
    payload: UpdateApplicationRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[ApplicationRepository, Depends(get_application_repo)],
) -> ApplicationResponse:
    """Update lifecycle status, notes, or attached tailored document."""
    current = await repo.get_application(user_id=user_id, application_id=application_id)
    if not current:
        raise NotFoundError(resource=f"Application {application_id}")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return ApplicationResponse.model_validate(current)

    updated = await repo.update_application(
        user_id=user_id,
        application_id=application_id,
        updates=updates,
    )
    if not updated:
        raise NotFoundError(resource=f"Application {application_id}")

    # If status changed, log audit event
    if payload.status and payload.status != current.get("status"):
        await repo.add_application_event(
            application_id=application_id,
            user_id=user_id,
            event_type="status_change",
            from_status=current.get("status"),
            to_status=payload.status,
            note=f"Status transitioned to '{payload.status}'",
        )

    return ApplicationResponse.model_validate(updated)


@router.post(
    "/{application_id}/events",
    response_model=ApplicationEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log a timeline event on an application",
)
async def add_application_event(
    application_id: UUID,
    payload: AddApplicationEventRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[ApplicationRepository, Depends(get_application_repo)],
) -> ApplicationEventResponse:
    """Append a timeline entry (e.g. interview scheduled, follow-up note)."""
    current = await repo.get_application(user_id=user_id, application_id=application_id)
    if not current:
        raise NotFoundError(resource=f"Application {application_id}")

    event = await repo.add_application_event(
        application_id=application_id,
        user_id=user_id,
        to_status=current.get("status", "saved"),
        note=payload.note,
        event_type=payload.event_type,
        event_data=payload.event_data,
    )
    return ApplicationEventResponse.model_validate(event)


@router.get(
    "/{application_id}/events",
    response_model=list[ApplicationEventResponse],
    summary="List timeline history events for an application",
)
async def list_application_events(
    application_id: UUID,
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[ApplicationRepository, Depends(get_application_repo)],
) -> list[ApplicationEventResponse]:
    """Retrieve all chronological events for an application."""
    events = await repo.list_application_events(user_id=user_id, application_id=application_id)
    return [ApplicationEventResponse.model_validate(e) for e in events]
