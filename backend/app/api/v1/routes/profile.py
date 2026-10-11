"""
Profile API endpoints.

Endpoints:
- GET /api/v1/profile (profile metadata + active version)
- PATCH /api/v1/profile (update profile details)
- GET /api/v1/profile/versions (list profile versions)
- GET /api/v1/profile/versions/{version_id} (version detail + evidence claims)
- POST /api/v1/profile/versions/{version_id}/confirm (confirm version)
- GET /api/v1/profile/preferences (get search preferences)
- PUT /api/v1/profile/preferences (update search preferences)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends

from app.api.dependencies import CurrentUser
from app.core.exceptions import NotFoundError
from app.repositories.profile_repository import ProfileRepository
from app.repositories.search_preferences_repository import SearchPreferencesRepository
from app.schemas.profile import (
    ProfileVersionDetail,
    SearchPreferencesPayload,
    SearchPreferencesResponse,
    UserProfileResponse,
    UserProfileUpdate,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


def get_profile_repo() -> ProfileRepository:
    return ProfileRepository()


def get_preferences_repo() -> SearchPreferencesRepository:
    return SearchPreferencesRepository()


@router.get(
    "",
    summary="Get user profile",
    description="Retrieve the authenticated candidate's profile and their active profile version.",
)
async def get_user_profile(
    current_user: CurrentUser,
    repo: ProfileRepository = Depends(get_profile_repo),
) -> dict[str, Any]:
    prof = await repo.get_profile(current_user)
    active_ver = await repo.get_active_profile_version(current_user)
    years_exp = active_ver.get("years_experience") if active_ver else None

    if prof and isinstance(prof, dict):
        prof["years_experience"] = years_exp

    return {
        "profile": prof,
        "active_version": active_ver,
        "years_experience": years_exp,
    }


@router.patch(
    "",
    response_model=UserProfileResponse,
    summary="Update user profile",
    description="Update profile contact info and metadata.",
)
async def update_user_profile(
    payload: UserProfileUpdate,
    current_user: CurrentUser,
    repo: ProfileRepository = Depends(get_profile_repo),
) -> dict[str, Any]:
    update_data = payload.model_dump(exclude_unset=True)
    years_exp = update_data.pop("years_experience", None)

    # Upsert standard profile contact details
    res = await repo.upsert_profile(current_user, update_data)

    # Update active profile version's years_experience if provided
    if years_exp is not None:
        await repo.update_active_years_experience(current_user, float(years_exp))
        res["years_experience"] = float(years_exp)
    else:
        active_ver = await repo.get_active_profile_version(current_user)
        if active_ver:
            res["years_experience"] = active_ver.get("years_experience")

    return res


@router.get(
    "/versions",
    summary="List profile versions",
    description="List all structured profile versions extracted for the candidate.",
)
async def list_profile_versions(
    current_user: CurrentUser,
    repo: ProfileRepository = Depends(get_profile_repo),
) -> list[dict[str, Any]]:
    # Query all profile versions for user
    res = (
        repo.client.table("profile_versions")
        .select("*")
        .eq("user_id", str(current_user))
        .order("version_number", desc=True)
        .execute()
    )
    return repo.cast_records(res.data)


@router.get(
    "/versions/{version_id}",
    response_model=ProfileVersionDetail,
    summary="Get profile version detail",
    description="Get specific profile version along with evidence provenance claims.",
)
async def get_profile_version_detail(
    version_id: UUID,
    current_user: CurrentUser,
    repo: ProfileRepository = Depends(get_profile_repo),
) -> dict[str, Any]:
    res = (
        repo.client.table("profile_versions")
        .select("*")
        .eq("user_id", str(current_user))
        .eq("id", str(version_id))
        .maybe_single()
        .execute()
    )
    version = repo.cast_single(res.data) if res else None
    if not version:
        raise NotFoundError("Profile version")

    evidence = await repo.get_profile_evidence(current_user, version_id)
    return {
        **version,
        "evidence": evidence,
    }


@router.post(
    "/versions/{version_id}/confirm",
    summary="Confirm profile version",
    description=(
        "Mark a profile version as confirmed by the candidate. "
        "Tailored resumes are grounded against confirmed versions."
    ),
)
async def confirm_profile_version(
    version_id: UUID,
    current_user: CurrentUser,
    repo: ProfileRepository = Depends(get_profile_repo),
) -> dict[str, Any]:
    confirmed = await repo.confirm_profile_version(current_user, version_id)
    return {
        "status": "confirmed",
        "profile_version": confirmed,
    }


@router.get(
    "/preferences",
    response_model=SearchPreferencesResponse | None,
    summary="Get search preferences",
    description="Retrieve candidate job search preferences.",
)
async def get_search_preferences(
    current_user: CurrentUser,
    repo: SearchPreferencesRepository = Depends(get_preferences_repo),
) -> dict[str, Any] | None:
    return await repo.get_preferences(current_user)


@router.put(
    "/preferences",
    response_model=SearchPreferencesResponse,
    summary="Update search preferences",
    description="Save or update candidate job search preferences.",
)
async def update_search_preferences(
    payload: SearchPreferencesPayload,
    current_user: CurrentUser,
    repo: SearchPreferencesRepository = Depends(get_preferences_repo),
) -> dict[str, Any]:
    return await repo.upsert_preferences(current_user, payload.model_dump())
