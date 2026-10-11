"""
Repository for the PostgreSQL durable task queue.

Enforces:
- Idempotency via unique idempotency_key constraints.
- Multi-user isolation for task reads.
- Atomic task claiming and crash recovery.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import structlog

from app.core.exceptions import NotFoundError, ProviderError
from app.repositories.base import BaseRepository

log = structlog.get_logger(__name__)


class TaskRepository(BaseRepository):
    """Repository handling asynchronous tasks stored in PostgreSQL."""

    async def enqueue_task(
        self,
        user_id: UUID | str,
        task_type: str,
        payload: dict[str, Any],
        reference_id: UUID | str | None = None,
        idempotency_key: str | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Enqueue a background task.

        If idempotency_key is provided and exists, returns the existing task
        without duplicate execution.
        """
        uid = self.ensure_uuid_str(user_id)

        # Check existing idempotency key
        if idempotency_key:
            try:
                existing = (
                    self.client.table("tasks")
                    .select("*")
                    .eq("user_id", uid)
                    .eq("idempotency_key", idempotency_key)
                    .maybe_single()
                    .execute()
                )
                single = self.cast_single(existing.data) if existing else None
                if single:
                    log.info("task_idempotent_duplicate_returned", key=idempotency_key)
                    return single
            except Exception as exc:
                log.warning("idempotency_check_error", error=str(exc))

        task_record = {
            "user_id": uid,
            "task_type": task_type,
            "payload": payload,
            "reference_id": self.ensure_uuid_str(reference_id) if reference_id else None,
            "idempotency_key": idempotency_key,
            "status": "pending",
            "retry_count": 0,
            "max_retries": max_retries,
        }

        try:
            res = self.client.table("tasks").insert(task_record).execute()
            records = self.cast_records(res.data)
            if not records:
                raise ProviderError(provider="Database", detail="Failed to enqueue task.")
            return records[0]
        except Exception as exc:
            log.error("repo_enqueue_task_failed", user_id=uid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def get_task(self, user_id: UUID | str, task_id: UUID | str) -> dict[str, Any] | None:
        """Fetch task details for a user with ownership check."""
        uid = self.ensure_uuid_str(user_id)
        tid = self.ensure_uuid_str(task_id)
        try:
            res = (
                self.client.table("tasks")
                .select("*")
                .eq("user_id", uid)
                .eq("id", tid)
                .maybe_single()
                .execute()
            )
            return self.cast_single(res.data) if res else None
        except Exception as exc:
            log.error("repo_get_task_failed", user_id=uid, task_id=tid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def claim_next_task(self, worker_id: str) -> dict[str, Any] | None:
        """
        Worker operation: Claim the next pending task for execution.

        Selects oldest pending task and atomically updates status to 'running'.
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            pending = (
                self.client.table("tasks")
                .select("*")
                .eq("status", "pending")
                .order("created_at", desc=False)
                .limit(1)
                .execute()
            )
            records = self.cast_records(pending.data)
            if not records:
                return None

            task = records[0]
            task_id = str(task["id"])

            res = (
                self.client.table("tasks")
                .update(
                    {
                        "status": "running",
                        "claimed_by": worker_id,
                        "claimed_at": now,
                        "started_at": now,
                    }
                )
                .eq("id", task_id)
                .eq("status", "pending")
                .execute()
            )
            claimed = self.cast_records(res.data)
            return claimed[0] if claimed else None
        except Exception as exc:
            log.error("repo_claim_task_failed", worker_id=worker_id, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def complete_task(
        self, task_id: UUID | str, result: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Mark a task as completed with results."""
        tid = self.ensure_uuid_str(task_id)
        now = datetime.now(timezone.utc).isoformat()
        try:
            res = (
                self.client.table("tasks")
                .update(
                    {
                        "status": "completed",
                        "completed_at": now,
                        "result": result or {},
                    }
                )
                .eq("id", tid)
                .execute()
            )
            records = self.cast_records(res.data)
            if not records:
                raise NotFoundError("Task")
            return records[0]
        except NotFoundError:
            raise
        except Exception as exc:
            log.error("repo_complete_task_failed", task_id=tid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def fail_task(
        self,
        task_id: UUID | str,
        error_message: str,
    ) -> dict[str, Any]:
        """Mark a task as failed or increment retry count if retries remain."""
        tid = self.ensure_uuid_str(task_id)
        now = datetime.now(timezone.utc).isoformat()
        try:
            current = (
                self.client.table("tasks")
                .select("retry_count", "max_retries")
                .eq("id", tid)
                .maybe_single()
                .execute()
            )
            single = self.cast_single(current.data) if current else None
            if not single:
                raise NotFoundError("Task")

            raw_retry = single.get("retry_count", 0)
            retry_count = int(raw_retry) if isinstance(raw_retry, (int, float, str)) else 0
            raw_max = single.get("max_retries", 3)
            max_retries = int(raw_max) if isinstance(raw_max, (int, float, str)) else 3

            if retry_count + 1 < max_retries:
                update_data = {
                    "status": "pending",
                    "retry_count": retry_count + 1,
                    "error_message": error_message,
                    "claimed_by": None,
                    "claimed_at": None,
                }
            else:
                update_data = {
                    "status": "failed",
                    "error_message": error_message,
                    "completed_at": now,
                }

            res = self.client.table("tasks").update(update_data).eq("id", tid).execute()
            records = self.cast_records(res.data)
            if not records:
                raise NotFoundError("Task")
            return records[0]
        except NotFoundError:
            raise
        except Exception as exc:
            log.error("repo_fail_task_failed", task_id=tid, error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc

    async def recover_stale_tasks(self, timeout_seconds: int = 300) -> int:
        """Worker maintenance: Reclaim tasks stuck in 'running' state past the timeout."""
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)).isoformat()
        try:
            stale = (
                self.client.table("tasks")
                .select("id")
                .eq("status", "running")
                .lt("claimed_at", cutoff)
                .execute()
            )
            records = self.cast_records(stale.data)
            recovered_count = 0
            for row in records:
                row_id = row.get("id")
                if row_id:
                    await self.fail_task(
                        str(row_id), error_message="Worker timeout / stale task recovery"
                    )
                    recovered_count += 1
            if recovered_count:
                log.info("stale_tasks_recovered", count=recovered_count)
            return recovered_count
        except Exception as exc:
            log.error("repo_recover_stale_tasks_failed", error=str(exc))
            raise ProviderError(provider="Database", detail=str(exc)) from exc
