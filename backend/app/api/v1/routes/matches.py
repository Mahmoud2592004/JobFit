"""
API endpoints for job match evaluation, explainability breakdown, and saving.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user
from app.api.v1.routes.jobs import get_job_repository
from app.api.v1.routes.profile import get_profile_repo
from app.core.exceptions import NotFoundError
from app.repositories.job_match_repository import JobMatchRepository
from app.repositories.job_repository import JobRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.match import (
    BatchMatchRequest,
    BatchMatchResponse,
    JobMatchResponse,
)
from app.services.matching_service import MatchingService

router = APIRouter(prefix="/matches", tags=["Matches"])


def get_match_repository() -> JobMatchRepository:
    """Dependency factory for JobMatchRepository."""
    return JobMatchRepository()


def get_matching_service(
    match_repo: Annotated[JobMatchRepository, Depends(get_match_repository)],
    job_repo: Annotated[JobRepository, Depends(get_job_repository)],
    profile_repo: Annotated[ProfileRepository, Depends(get_profile_repo)],
) -> MatchingService:
    """Dependency factory for MatchingService."""
    return MatchingService(
        match_repo=match_repo,
        job_repo=job_repo,
        profile_repo=profile_repo,
    )


@router.post(
    "/batch",
    response_model=BatchMatchResponse,
    summary="Batch evaluate job matches for active profile",
)
async def evaluate_batch_matches(
    payload: BatchMatchRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[MatchingService, Depends(get_matching_service)],
) -> BatchMatchResponse:
    """Evaluate compatibility scores and explanations for a list of jobs."""
    matches = await service.batch_match_jobs(
        user_id=user_id,
        job_ids=payload.job_ids,
        search_run_id=payload.search_run_id,
    )
    return BatchMatchResponse(
        evaluated_count=len(matches),
        matches=[JobMatchResponse.model_validate(m) for m in matches],
    )


@router.post(
    "/evaluate/{job_id}",
    response_model=JobMatchResponse,
    summary="Evaluate compatibility match for a specific job",
)
async def evaluate_single_match(
    job_id: UUID,
    user_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[MatchingService, Depends(get_matching_service)],
) -> JobMatchResponse:
    """Evaluate candidate compatibility against a specific job listing."""
    match = await service.match_job_for_user(
        user_id=user_id,
        job_id=job_id,
    )
    return JobMatchResponse.model_validate(match)


@router.get(
    "",
    response_model=list[JobMatchResponse],
    summary="List evaluated matches for current user",
)
async def list_matches(
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[JobMatchRepository, Depends(get_match_repository)],
    min_score: Annotated[float | None, Query(ge=0.0, le=100.0)] = None,
    is_saved: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[JobMatchResponse]:
    """Retrieve scored matches ordered by score descending."""
    records = await repo.list_matches(
        user_id=user_id,
        min_score=min_score,
        is_saved=is_saved,
        limit=limit,
        offset=offset,
    )
    return [JobMatchResponse.model_validate(r) for r in records]


@router.get(
    "/{match_id}",
    response_model=JobMatchResponse,
    summary="Get match details and explainability breakdown",
)
async def get_match(
    match_id: UUID,
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[JobMatchRepository, Depends(get_match_repository)],
) -> JobMatchResponse:
    """Retrieve full score breakdown and evidence for a specific match."""
    record = await repo.get_match(user_id=user_id, match_id=match_id)
    if not record:
        raise NotFoundError(resource=f"Job match {match_id}")
    return JobMatchResponse.model_validate(record)


@router.post(
    "/{match_id}/save",
    response_model=JobMatchResponse,
    summary="Save / bookmark a matched job",
)
async def save_match(
    match_id: UUID,
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[JobMatchRepository, Depends(get_match_repository)],
) -> JobMatchResponse:
    """Bookmark a match for easy filtering and tracking."""
    record = await repo.set_saved_status(user_id=user_id, match_id=match_id, is_saved=True)
    if not record:
        raise NotFoundError(resource=f"Job match {match_id}")
    return JobMatchResponse.model_validate(record)


@router.delete(
    "/{match_id}/save",
    response_model=JobMatchResponse,
    summary="Unsave / unbookmark a matched job",
)
async def unsave_match(
    match_id: UUID,
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[JobMatchRepository, Depends(get_match_repository)],
) -> JobMatchResponse:
    """Remove bookmark on a match."""
    record = await repo.set_saved_status(user_id=user_id, match_id=match_id, is_saved=False)
    if not record:
        raise NotFoundError(resource=f"Job match {match_id}")
    return JobMatchResponse.model_validate(record)
