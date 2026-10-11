"""
Data access repository for tailored resume documents.
Enforces strict user isolation across all read, write, and update operations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog

from app.core.exceptions import ProviderError
from app.repositories.base import BaseRepository

log = structlog.get_logger(__name__)


class TailoredDocumentRepository(BaseRepository):
    """Repository handling tailored documents persistence and retrieval."""

    async def create_document(
        self,
        user_id: UUID | str,
        job_id: UUID | str,
        profile_version_id: UUID | str,
        template_version: str = "modern-clean-v1",
        status: str = "pending",
    ) -> dict[str, Any]:
        """Insert a initial tailored document record."""
        uid = self.ensure_uuid_str(user_id)
        jid = self.ensure_uuid_str(job_id)
        pvid = self.ensure_uuid_str(profile_version_id)

        record = {
            "user_id": uid,
            "job_id": jid,
            "profile_version_id": pvid,
            "template_version": template_version,
            "status": status,
            "flagged_claims": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            res = self.client.table("tailored_documents").insert(record).execute()
            records = self.cast_records(res.data)
            return records[0] if records else record
        except Exception as exc:
            log.error("create_tailored_doc_failed", user_id=uid, job_id=jid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def update_document(
        self,
        doc_id: UUID | str,
        user_id: UUID | str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update a tailored document, ensuring user ownership."""
        did = self.ensure_uuid_str(doc_id)
        uid = self.ensure_uuid_str(user_id)

        payload = {**updates, "updated_at": datetime.now(timezone.utc).isoformat()}

        try:
            res = (
                self.client.table("tailored_documents")
                .update(payload)
                .eq("id", did)
                .eq("user_id", uid)
                .execute()
            )
            records = self.cast_records(res.data)
            return records[0] if records else None
        except Exception as exc:
            log.error("update_tailored_doc_failed", doc_id=did, user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def get_document(
        self,
        user_id: UUID | str,
        doc_id: UUID | str,
    ) -> dict[str, Any] | None:
        """Retrieve a specific tailored document by UUID with user isolation."""
        did = self.ensure_uuid_str(doc_id)
        uid = self.ensure_uuid_str(user_id)

        try:
            res = (
                self.client.table("tailored_documents")
                .select("*")
                .eq("id", did)
                .eq("user_id", uid)
                .limit(1)
                .execute()
            )
            records = self.cast_records(res.data)
            return records[0] if records else None
        except Exception as exc:
            log.error("get_tailored_doc_failed", doc_id=did, user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def list_documents(
        self,
        user_id: UUID | str,
        job_id: UUID | str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List tailored documents for user, optionally filtered by job_id."""
        uid = self.ensure_uuid_str(user_id)

        try:
            builder = (
                self.client.table("tailored_documents")
                .select("*")
                .eq("user_id", uid)
                .order("created_at", desc=True)
            )

            if job_id:
                builder = builder.eq("job_id", self.ensure_uuid_str(job_id))

            builder = builder.limit(limit)
            res = builder.execute()
            return self.cast_records(res.data)
        except Exception as exc:
            log.error("list_tailored_docs_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc
