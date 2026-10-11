"""
API endpoints for job discovery, listing, detail, and search run history.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_current_user, get_optional_user
from app.core.exceptions import NotFoundError
from app.repositories.job_repository import JobRepository
from app.schemas.job import (
    JobAIFilterRequest,
    JobAIFilterResponse,
    JobResponse,
    JobSearchRequest,
    JobSearchResponse,
    SearchRunResponse,
)
from app.services.ai_job_filter_service import AIJobFilterService
from app.services.job_discovery_service import JobDiscoveryService

router = APIRouter(prefix="/jobs", tags=["Jobs"])
search_runs_router = APIRouter(prefix="/search-runs", tags=["Search Runs"])


def get_job_repository() -> JobRepository:
    """Dependency factory for JobRepository."""
    return JobRepository()


def get_job_discovery_service(
    repo: Annotated[JobRepository, Depends(get_job_repository)],
) -> JobDiscoveryService:
    """Dependency factory for JobDiscoveryService."""
    return JobDiscoveryService(job_repo=repo)


def get_ai_job_filter_service(
    job_repo: Annotated[JobRepository, Depends(get_job_repository)],
) -> AIJobFilterService:
    """Dependency factory for AIJobFilterService."""
    from app.repositories.profile_repository import ProfileRepository
    from app.repositories.search_preferences_repository import SearchPreferencesRepository

    return AIJobFilterService(
        job_repo=job_repo,
        profile_repo=ProfileRepository(),
        preferences_repo=SearchPreferencesRepository(),
    )


@router.post(
    "/search",
    response_model=JobSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger on-demand multi-source job discovery",
)
async def search_jobs(
    payload: JobSearchRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    discovery_service: Annotated[JobDiscoveryService, Depends(get_job_discovery_service)],
) -> JobSearchResponse:
    """
    Search external job sources (LinkedIn via Apify, etc.) concurrently,
    deduplicate results, persist new listings to the shared jobs catalog,
    and log a user search run audit entry.
    """
    request_prefs: dict[str, Any] = {}
    if payload.location:
        request_prefs["location"] = payload.location
        request_prefs["locations"] = [payload.location]
    if payload.urls:
        request_prefs["urls"] = payload.urls
    if payload.geo_id:
        request_prefs["geo_id"] = payload.geo_id
    if payload.distance is not None:
        request_prefs["distance"] = payload.distance
    if payload.date_posted:
        request_prefs["date_posted"] = payload.date_posted
    if payload.company_ids:
        request_prefs["company_ids"] = payload.company_ids
    if payload.under_10_applicants:
        request_prefs["under_10_applicants"] = True
    if payload.remote_only:
        request_prefs["work_arrangements"] = ["remote"]
        request_prefs["remote_only"] = True
    request_prefs["auto_convert_to_ai_search"] = payload.auto_convert_to_ai_search
    request_prefs["scrape_company"] = payload.scrape_company
    request_prefs["split_by_location"] = payload.split_by_location
    if payload.split_country:
        request_prefs["split_country"] = payload.split_country
    if payload.limit_per_provider:
        request_prefs["limit_per_source"] = payload.limit_per_provider

    result = await discovery_service.discover_jobs(
        user_id=user_id,
        query=payload.query or "",
        remote_only=payload.remote_only,
        limit_per_provider=payload.limit_per_provider,
        preferences=request_prefs or None,
    )
    return JobSearchResponse.model_validate(result)


@router.post(
    "/ai-filter",
    response_model=JobAIFilterResponse,
    status_code=status.HTTP_200_OK,
    summary="Search and filter jobs using Gemini AI grounded in user experience & preferences",
)
async def ai_filter_jobs(
    payload: JobAIFilterRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    ai_service: Annotated[AIJobFilterService, Depends(get_ai_job_filter_service)],
) -> JobAIFilterResponse:
    """
    Rigorously evaluate candidate fit against job listings using Gemini.
    Incorporates candidate's verified years of experience and work preferences.
    """
    return await ai_service.filter_jobs_for_candidate(
        user_id=user_id,
        query=payload.query,
        location=payload.location,
        work_arrangement=payload.work_arrangement,
        date_posted=payload.date_posted,
        experience_level=payload.experience_level,
        employment_type=payload.employment_type,
        min_fit=payload.min_fit,
        limit=payload.limit,
    )


@router.get(
    "",
    response_model=list[JobResponse],
    summary="List and filter catalog jobs",
)
async def list_jobs(
    repo: Annotated[JobRepository, Depends(get_job_repository)],
    _user_id: Annotated[str | None, Depends(get_optional_user)] = None,
    query: Annotated[str | None, Query(description="Filter by title or employer")] = None,
    remote_only: Annotated[bool, Query(description="Filter remote-only listings")] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[JobResponse]:
    """Return paginated job listings from the catalog matching optional criteria."""
    records = await repo.list_jobs(
        query=query,
        remote_only=remote_only,
        limit=limit,
        offset=offset,
    )
    return [JobResponse.model_validate(r) for r in records]


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job listing details",
)
async def get_job(
    job_id: UUID,
    repo: Annotated[JobRepository, Depends(get_job_repository)],
    _user_id: Annotated[str | None, Depends(get_optional_user)] = None,
) -> JobResponse:
    """Retrieve full details of a specific job listing by UUID."""
    record = await repo.get_job(job_id)
    if not record:
        raise NotFoundError(resource=f"Job listing {job_id}")
    return JobResponse.model_validate(record)


@search_runs_router.get(
    "",
    response_model=list[SearchRunResponse],
    summary="List past search runs for current user",
)
async def list_search_runs(
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[JobRepository, Depends(get_job_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[SearchRunResponse]:
    """Retrieve discovery run history for the authenticated user."""
    records = await repo.list_search_runs(user_id=user_id, limit=limit)
    return [SearchRunResponse.model_validate(r) for r in records]


@search_runs_router.delete(
    "/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a past search run for current user",
)
async def delete_search_run(
    run_id: UUID,
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[JobRepository, Depends(get_job_repository)],
) -> None:
    """Delete a past search run."""
    await repo.delete_search_run(user_id=user_id, run_id=run_id)

