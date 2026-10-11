"""
API endpoints for asynchronous task inspection and submission.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.repositories.task_repository import TaskRepository
from app.schemas.task import EnqueueTaskRequest, TaskResponse

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_task_repo() -> TaskRepository:
    """Dependency factory for TaskRepository."""
    return TaskRepository()


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue an asynchronous task",
)
async def enqueue_task(
    payload: EnqueueTaskRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[TaskRepository, Depends(get_task_repo)],
) -> TaskResponse:
    """Enqueue a long-running background task."""
    task_data = await repo.enqueue_task(
        user_id=user_id,
        task_type=payload.task_type,
        payload=payload.payload,
        idempotency_key=payload.idempotency_key,
        max_retries=payload.max_retries,
    )
    return TaskResponse.model_validate(task_data)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get background task status and result",
)
async def get_task(
    task_id: UUID,
    user_id: Annotated[str, Depends(get_current_user)],
    repo: Annotated[TaskRepository, Depends(get_task_repo)],
) -> TaskResponse:
    """Inspect status, execution logs, and result of a background task."""
    task_data = await repo.get_task(user_id=user_id, task_id=task_id)
    if not task_data:
        raise NotFoundError(resource=f"Task {task_id}")
    return TaskResponse.model_validate(task_data)
