"""
Data access repository for job application tracking and audit events.
Enforces strict user isolation across all CRUD operations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog

from app.core.exceptions import ProviderError
from app.repositories.base import BaseRepository

log = structlog.get_logger(__name__)


class ApplicationRepository(BaseRepository):
    """Repository handling job applications and timeline events."""

    async def create_application(
        self,
        user_id: UUID | str,
        job_id: UUID | str,
        tailored_document_id: UUID | str | None = None,
        status: str = "saved",
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Create a new job application tracking record."""
        uid = self.ensure_uuid_str(user_id)
        jid = self.ensure_uuid_str(job_id)
        tdid = self.ensure_uuid_str(tailored_document_id) if tailored_document_id else None
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "user_id": uid,
            "job_id": jid,
            "tailored_document_id": tdid,
            "status": status,
            "notes": notes,
            "applied_at": now if status == "applied" else None,
            "created_at": now,
            "updated_at": now,
        }

        try:
            res = (
                self.client.table("applications")
                .upsert(record, on_conflict="user_id,job_id")
                .execute()
            )
            records = self.cast_records(res.data)
            created = records[0] if records else record

            # Log initial event
            await self.add_application_event(
                application_id=created.get("id") or str(jid),
                user_id=uid,
                from_status=None,
                to_status=status,
                note=f"Application tracked with status '{status}'",
            )
            return created
        except Exception as exc:
            log.error("create_application_failed", user_id=uid, job_id=jid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def update_application(
        self,
        user_id: UUID | str,
        application_id: UUID | str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update status, notes, or document on an application."""
        uid = self.ensure_uuid_str(user_id)
        aid = self.ensure_uuid_str(application_id)
        now = datetime.now(timezone.utc).isoformat()

        payload = {**updates, "updated_at": now}

        try:
            res = (
                self.client.table("applications")
                .update(payload)
                .eq("id", aid)
                .eq("user_id", uid)
                .execute()
            )
            records = self.cast_records(res.data)
            return records[0] if records else None
        except Exception as exc:
            log.error("update_application_failed", application_id=aid, user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def get_application(
        self,
        user_id: UUID | str,
        application_id: UUID | str,
    ) -> dict[str, Any] | None:
        """Fetch application details with attached job listing data."""
        uid = self.ensure_uuid_str(user_id)
        aid = self.ensure_uuid_str(application_id)

        try:
            res = (
                self.client.table("applications")
                .select("*, job:jobs(*)")
                .eq("id", aid)
                .eq("user_id", uid)
                .limit(1)
                .execute()
            )
            records = self.cast_records(res.data)
            return records[0] if records else None
        except Exception as exc:
            log.error("get_application_failed", application_id=aid, user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def list_applications(
        self,
        user_id: UUID | str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List user applications ordered by updated_at descending."""
        uid = self.ensure_uuid_str(user_id)

        try:
            builder = (
                self.client.table("applications")
                .select("*, job:jobs(*)")
                .eq("user_id", uid)
                .order("updated_at", desc=True)
            )

            if status:
                builder = builder.eq("status", status)

            builder = builder.range(offset, offset + limit - 1)
            res = builder.execute()
            return self.cast_records(res.data)
        except Exception as exc:
            log.error("list_applications_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def add_application_event(
        self,
        application_id: UUID | str,
        user_id: UUID | str,
        to_status: str,
        from_status: str | None = None,
        note: str | None = None,
        event_type: str | None = None,
        event_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record an event in the application history timeline."""
        aid = self.ensure_uuid_str(application_id)
        uid = self.ensure_uuid_str(user_id)
        now = datetime.now(timezone.utc).isoformat()

        # If note is not set but event_type is, use event_type in note
        effective_note = note
        if not effective_note and event_type:
            effective_note = f"Event: {event_type}"
        if event_data and effective_note:
            effective_note = f"{effective_note} ({event_data})"
        elif event_data and not effective_note:
            effective_note = str(event_data)

        record = {
            "application_id": aid,
            "user_id": uid,
            "from_status": from_status,
            "to_status": to_status,
            "note": effective_note,
            "occurred_at": now,
        }

        try:
            res = self.client.table("application_events").insert(record).execute()
            records = self.cast_records(res.data)
            return records[0] if records else record
        except Exception as exc:
            log.error("add_application_event_failed", application_id=aid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def list_application_events(
        self,
        user_id: UUID | str,
        application_id: UUID | str,
    ) -> list[dict[str, Any]]:
        """Retrieve chronological history events for an application."""
        uid = self.ensure_uuid_str(user_id)
        aid = self.ensure_uuid_str(application_id)

        try:
            res = (
                self.client.table("application_events")
                .select("*")
                .eq("user_id", uid)
                .eq("application_id", aid)
                .order("occurred_at", desc=False)
                .execute()
            )
            return self.cast_records(res.data)
        except Exception as exc:
            log.error("list_application_events_failed", application_id=aid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc
