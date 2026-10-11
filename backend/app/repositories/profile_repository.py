"""
Profile repository for candidate profiles, resume versions, and evidence claims.

Enforces strict user isolation — every operation filters by user_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog

from app.core.exceptions import NotFoundError, ProviderError
from app.repositories.base import BaseRepository

log = structlog.get_logger(__name__)


class ProfileRepository(BaseRepository):
    """Repository handling profiles, resumes, profile versions, and evidence."""

    async def get_profile(self, user_id: UUID | str) -> dict[str, Any] | None:
        """Fetch candidate profile for user."""
        uid = self.ensure_uuid_str(user_id)
        try:
            res = (
                self.client.table("profiles")
                .select("*")
                .eq("user_id", uid)
                .maybe_single()
                .execute()
            )
            return self.cast_single(res.data) if res else None
        except Exception as exc:
            log.error("repo_get_profile_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def upsert_profile(self, user_id: UUID | str, data: dict[str, Any]) -> dict[str, Any]:
        """Create or update user profile."""
        uid = self.ensure_uuid_str(user_id)
        payload = {
            **data,
            "user_id": uid,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            res = self.client.table("profiles").upsert(payload, on_conflict="user_id").execute()
            records = self.cast_records(res.data)
            if not records:
                raise ProviderError(provider="Database", detail="Failed to upsert profile.")
            return records[0]
        except Exception as exc:
            log.error("repo_upsert_profile_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def create_resume_version(
        self,
        user_id: UUID | str,
        source_type: str,
        storage_path: str | None = None,
        raw_text: str | None = None,
        file_size_bytes: int | None = None,
        original_filename: str | None = None,
    ) -> dict[str, Any]:
        """Create a new resume version entry."""
        uid = self.ensure_uuid_str(user_id)
        try:
            existing = (
                self.client.table("resume_versions")
                .select("version_number")
                .eq("user_id", uid)
                .order("version_number", desc=True)
                .limit(1)
                .execute()
            )
            existing_records = self.cast_records(existing.data)
            next_version = (existing_records[0]["version_number"] + 1) if existing_records else 1

            record = {
                "user_id": uid,
                "version_number": next_version,
                "source_type": source_type,
                "storage_path": storage_path,
                "raw_text": raw_text,
                "file_size_bytes": file_size_bytes,
                "original_filename": original_filename,
                "extraction_status": "pending",
            }
            res = self.client.table("resume_versions").insert(record).execute()
            records = self.cast_records(res.data)
            if not records:
                raise ProviderError(provider="Database", detail="Failed to create resume version.")
            return records[0]
        except Exception as exc:
            log.error("repo_create_resume_version_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def get_resume_versions(self, user_id: UUID | str) -> list[dict[str, Any]]:
        """List all resume versions for a user ordered by version descending."""
        uid = self.ensure_uuid_str(user_id)
        try:
            res = (
                self.client.table("resume_versions")
                .select("*")
                .eq("user_id", uid)
                .order("version_number", desc=True)
                .execute()
            )
            return self.cast_records(res.data)
        except Exception as exc:
            log.error("repo_get_resume_versions_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def get_resume_version(
        self, user_id: UUID | str, version_id: UUID | str
    ) -> dict[str, Any] | None:
        """Fetch a specific resume version owned by the user."""
        uid = self.ensure_uuid_str(user_id)
        vid = self.ensure_uuid_str(version_id)
        try:
            res = (
                self.client.table("resume_versions")
                .select("*")
                .eq("user_id", uid)
                .eq("id", vid)
                .maybe_single()
                .execute()
            )
            return self.cast_single(res.data) if res else None
        except Exception as exc:
            log.error("repo_get_resume_version_failed", user_id=uid, version_id=vid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def update_resume_extraction(
        self,
        user_id: UUID | str,
        resume_version_id: UUID | str,
        status: str,
        error: str | None = None,
        raw_text: str | None = None,
    ) -> dict[str, Any]:
        """Update extraction status and optional raw text."""
        uid = self.ensure_uuid_str(user_id)
        vid = self.ensure_uuid_str(resume_version_id)
        update_data: dict[str, Any] = {"extraction_status": status}
        if error is not None:
            update_data["extraction_error"] = error
        if raw_text is not None:
            update_data["raw_text"] = raw_text

        try:
            res = (
                self.client.table("resume_versions")
                .update(update_data)
                .eq("user_id", uid)
                .eq("id", vid)
                .execute()
            )
            records = self.cast_records(res.data)
            if not records:
                raise NotFoundError("Resume version")
            return records[0]
        except NotFoundError:
            raise
        except Exception as exc:
            log.error("repo_update_resume_extraction_failed", error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def create_profile_version(
        self,
        user_id: UUID | str,
        resume_version_id: UUID | str | None = None,
        content: dict[str, Any] | None = None,
        skills: list[str] | None = None,
        target_roles: list[str] | None = None,
        seniority_level: str | None = None,
        years_experience: float | None = None,
    ) -> dict[str, Any]:
        """Create a new profile version extracted from resume."""
        uid = self.ensure_uuid_str(user_id)
        try:
            existing = (
                self.client.table("profile_versions")
                .select("version_number")
                .eq("user_id", uid)
                .order("version_number", desc=True)
                .limit(1)
                .execute()
            )
            existing_records = self.cast_records(existing.data)
            next_version = (existing_records[0]["version_number"] + 1) if existing_records else 1

            record = {
                "user_id": uid,
                "resume_version_id": (
                    self.ensure_uuid_str(resume_version_id) if resume_version_id else None
                ),
                "version_number": next_version,
                "is_confirmed": False,
                "content": content or {},
                "skills": skills or [],
                "target_roles": target_roles or [],
                "seniority_level": seniority_level or "unknown",
                "years_experience": years_experience,
            }
            res = self.client.table("profile_versions").insert(record).execute()
            records = self.cast_records(res.data)
            if not records:
                raise ProviderError(provider="Database", detail="Failed to create profile version.")
            return records[0]
        except Exception as exc:
            log.error("repo_create_profile_version_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def get_active_profile_version(self, user_id: UUID | str) -> dict[str, Any] | None:
        """Fetch the most recent confirmed profile version, or latest pending if none confirmed."""
        uid = self.ensure_uuid_str(user_id)
        try:
            # First check for confirmed version
            confirmed = (
                self.client.table("profile_versions")
                .select("*")
                .eq("user_id", uid)
                .eq("is_confirmed", True)
                .order("version_number", desc=True)
                .limit(1)
                .execute()
            )
            confirmed_records = self.cast_records(confirmed.data)
            if confirmed_records:
                return confirmed_records[0]

            # Fallback to latest unconfirmed version
            latest = (
                self.client.table("profile_versions")
                .select("*")
                .eq("user_id", uid)
                .order("version_number", desc=True)
                .limit(1)
                .execute()
            )
            latest_records = self.cast_records(latest.data)
            return latest_records[0] if latest_records else None
        except Exception as exc:
            log.error("repo_get_active_profile_version_failed", user_id=uid, error=str(exc))

    async def get_profile_version(
        self, user_id: UUID | str, version_id: UUID | str
    ) -> dict[str, Any] | None:
        """Fetch a specific profile version owned by the user."""
        uid = self.ensure_uuid_str(user_id)
        vid = self.ensure_uuid_str(version_id)
        try:
            res = (
                self.client.table("profile_versions")
                .select("*")
                .eq("user_id", uid)
                .eq("id", vid)
                .maybe_single()
                .execute()
            )
            return self.cast_single(res.data) if res else None
        except Exception as exc:
            log.error(
                "repo_get_profile_version_failed",
                user_id=uid,
                version_id=vid,
                error=str(exc),
            )
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def get_profile_versions(self, user_id: UUID | str) -> list[dict[str, Any]]:
        """List all profile versions for a user ordered by version descending."""
        uid = self.ensure_uuid_str(user_id)
        try:
            res = (
                self.client.table("profile_versions")
                .select("*")
                .eq("user_id", uid)
                .order("version_number", desc=True)
                .execute()
            )
            return self.cast_records(res.data)
        except Exception as exc:
            log.error("repo_get_profile_versions_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def confirm_profile_version(
        self, user_id: UUID | str, version_id: UUID | str
    ) -> dict[str, Any]:
        """Mark a profile version as confirmed by the candidate."""
        uid = self.ensure_uuid_str(user_id)
        vid = self.ensure_uuid_str(version_id)
        try:
            res = (
                self.client.table("profile_versions")
                .update({"is_confirmed": True})
                .eq("user_id", uid)
                .eq("id", vid)
                .execute()
            )
            records = self.cast_records(res.data)
            if not records:
                raise NotFoundError("Profile version")
            return records[0]
        except NotFoundError:
            raise
        except Exception as exc:
            log.error(
                "repo_confirm_profile_version_failed",
                user_id=uid,
                version_id=vid,
                error=str(exc),
            )
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def add_profile_evidence(
        self,
        user_id: UUID | str,
        profile_version_id: UUID | str,
        claim_type: str,
        claim_value: str,
        confidence: str,
        source_text: str | None = None,
        source_location: str | None = None,
    ) -> dict[str, Any]:
        """Record provenance evidence supporting an extracted profile claim."""
        uid = self.ensure_uuid_str(user_id)
        pvid = self.ensure_uuid_str(profile_version_id)
        record = {
            "user_id": uid,
            "profile_version_id": pvid,
            "claim_type": claim_type,
            "claim_value": claim_value,
            "confidence": confidence,
            "source_text": source_text,
            "source_location": source_location,
        }
        try:
            res = self.client.table("profile_evidence").insert(record).execute()
            records = self.cast_records(res.data)
            if not records:
                raise ProviderError(provider="Database", detail="Failed to add profile evidence.")
            return records[0]
        except Exception as exc:
            log.error(
                "repo_add_evidence_failed",
                user_id=uid,
                profile_version_id=pvid,
                error=str(exc),
            )
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def get_profile_evidence(
        self, user_id: UUID | str, profile_version_id: UUID | str
    ) -> list[dict[str, Any]]:
        """Retrieve all provenance evidence rows for a profile version."""
        uid = self.ensure_uuid_str(user_id)
        pvid = self.ensure_uuid_str(profile_version_id)
        try:
            res = (
                self.client.table("profile_evidence")
                .select("*")
                .eq("user_id", uid)
                .eq("profile_version_id", pvid)
                .execute()
            )
            return self.cast_records(res.data)
        except Exception as exc:
            log.error(
                "repo_get_evidence_failed",
                user_id=uid,
                profile_version_id=pvid,
                error=str(exc),
            )
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def update_active_years_experience(
        self, user_id: UUID | str, years: float
    ) -> dict[str, Any] | None:
        """Update years_experience on the active profile version or create one if none exists."""
        uid = self.ensure_uuid_str(user_id)
        try:
            active_ver = await self.get_active_profile_version(uid)
            if active_ver:
                vid = str(active_ver["id"])
                content = active_ver.get("content") or {}
                if isinstance(content, dict):
                    content["years_experience"] = years
                res = (
                    self.client.table("profile_versions")
                    .update({"years_experience": years, "content": content})
                    .eq("id", vid)
                    .eq("user_id", uid)
                    .execute()
                )
                records = self.cast_records(res.data)
                return records[0] if records else active_ver

            return await self.create_profile_version(
                user_id=uid,
                content={"years_experience": years},
                years_experience=years,
            )
        except Exception as exc:
            log.error("repo_update_years_experience_failed", user_id=uid, error=str(exc))
            return None
