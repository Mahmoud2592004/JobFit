"""Tests for common Pydantic response models and envelopes."""

from __future__ import annotations

from app.schemas.common import (
    ErrorDetail,
    ErrorResponse,
    MessageResponse,
    PaginatedResponse,
    PaginationMeta,
    TaskResponse,
)


def test_pagination_meta_has_next():
    meta = PaginationMeta.create(page=1, page_size=20, total=45)
    assert meta.page == 1
    assert meta.page_size == 20
    assert meta.total == 45
    assert meta.has_next is True

    last_page = PaginationMeta.create(page=3, page_size=20, total=45)
    assert last_page.has_next is False

    exact_page = PaginationMeta.create(page=2, page_size=20, total=40)
    assert exact_page.has_next is False


def test_paginated_response():
    meta = PaginationMeta.create(page=1, page_size=2, total=3)
    resp = PaginatedResponse(data=["item1", "item2"], pagination=meta)
    assert resp.data == ["item1", "item2"]
    assert resp.pagination.has_next is True


def test_error_response():
    resp = ErrorResponse(
        error=ErrorDetail(code="bad_request", message="Invalid payload", request_id="req_1")
    )
    assert resp.error.code == "bad_request"
    assert resp.error.request_id == "req_1"


def test_message_and_task_responses():
    msg = MessageResponse(message="Success")
    assert msg.message == "Success"

    task = TaskResponse(task_id="t1", reference_id="r1")
    assert task.task_id == "t1"
    assert task.status == "pending"
