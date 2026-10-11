"""
Shared Pydantic response schemas used across all API endpoints.

Provides consistent envelope formats for all responses.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Standard error body."""

    code: str
    message: str
    request_id: str = ""


class ErrorResponse(BaseModel):
    """Envelope for all error responses."""

    error: ErrorDetail


class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses."""

    page: int
    page_size: int
    total: int
    has_next: bool

    @classmethod
    def create(cls, page: int, page_size: int, total: int) -> PaginationMeta:
        return cls(
            page=page,
            page_size=page_size,
            total=total,
            has_next=(page * page_size) < total,
        )


class PaginatedResponse(BaseModel, Generic[T]):
    """Envelope for paginated list responses."""

    data: list[T]
    pagination: PaginationMeta


class MessageResponse(BaseModel):
    """Simple message response for operations that return no data."""

    message: str


class TaskResponse(BaseModel):
    """Response for operations that enqueue an async task."""

    task_id: str
    reference_id: str
    status: str = "pending"
    message: str = "Task queued successfully."
