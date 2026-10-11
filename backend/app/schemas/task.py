"""
Pydantic contracts and schemas for asynchronous tasks.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

TaskStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


class EnqueueTaskRequest(BaseModel):
    """Payload to enqueue a background operation."""

    task_type: str = Field(description="Task identifier (e.g. tailor_resume, scrape_jobs)")
    payload: dict[str, Any] = Field(default_factory=dict, description="Task arguments")
    idempotency_key: str | None = Field(default=None, description="Optional deduplication key")
    max_retries: int = Field(default=3, ge=1, le=10)


class TaskResponse(BaseModel):
    """Response contract for background task inspection."""

    id: UUID
    user_id: UUID | None = None
    task_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus
    retry_count: int = 0
    max_retries: int = 3
    error_summary: str | None = None
    worker_id: str | None = None
    claimed_by: str | None = None
    claimed_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    run_after: datetime | None = None
    result: dict[str, Any] = Field(default_factory=dict)
