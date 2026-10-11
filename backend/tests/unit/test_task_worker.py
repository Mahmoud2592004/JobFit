"""Unit tests for TaskWorker async engine."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.repositories.task_repository import TaskRepository
from app.services.task_worker import TaskWorker


@pytest.mark.asyncio
async def test_task_worker_claim_and_execute_success():
    mock_repo = MagicMock(spec=TaskRepository)
    task_id = str(uuid4())
    task_record = {
        "id": task_id,
        "task_type": "custom_job",
        "payload": {"target": "data"},
        "status": "running",
    }
    mock_repo.claim_next_task = AsyncMock(return_value=task_record)
    mock_repo.complete_task = AsyncMock(return_value={**task_record, "status": "completed"})
    mock_repo.fail_task = AsyncMock()

    worker = TaskWorker(task_repo=mock_repo, worker_id="test-worker-1")

    # Register custom handler
    handler_called = False

    async def custom_handler(payload: dict) -> dict:
        nonlocal handler_called
        handler_called = True
        assert payload["target"] == "data"
        return {"processed": True}

    worker.register_handler("custom_job", custom_handler)

    did_process = await worker.process_one_task()

    assert did_process is True
    assert handler_called is True
    mock_repo.claim_next_task.assert_called_once_with(worker_id="test-worker-1")
    mock_repo.complete_task.assert_called_once_with(task_id=task_id, result={"processed": True})
    mock_repo.fail_task.assert_not_called()


@pytest.mark.asyncio
async def test_task_worker_no_pending_tasks():
    mock_repo = MagicMock(spec=TaskRepository)
    mock_repo.claim_next_task = AsyncMock(return_value=None)

    worker = TaskWorker(task_repo=mock_repo)
    did_process = await worker.process_one_task()

    assert did_process is False


@pytest.mark.asyncio
async def test_task_worker_missing_handler():
    mock_repo = MagicMock(spec=TaskRepository)
    task_id = str(uuid4())
    task_record = {
        "id": task_id,
        "task_type": "unregistered_task",
        "payload": {},
    }
    mock_repo.claim_next_task = AsyncMock(return_value=task_record)
    mock_repo.fail_task = AsyncMock(return_value={**task_record, "status": "failed"})

    worker = TaskWorker(task_repo=mock_repo)
    did_process = await worker.process_one_task()

    assert did_process is True
    mock_repo.fail_task.assert_called_once()
    assert "No handler registered" in mock_repo.fail_task.call_args.kwargs["error_message"]


@pytest.mark.asyncio
async def test_task_worker_handler_raises_exception():
    mock_repo = MagicMock(spec=TaskRepository)
    task_id = str(uuid4())
    task_record = {
        "id": task_id,
        "task_type": "faulty_task",
        "payload": {},
    }
    mock_repo.claim_next_task = AsyncMock(return_value=task_record)
    mock_repo.fail_task = AsyncMock(return_value={**task_record, "status": "failed"})

    async def exploding_handler(_payload: dict) -> dict:
        raise ValueError("Something went terribly wrong")

    worker = TaskWorker(task_repo=mock_repo)
    worker.register_handler("faulty_task", exploding_handler)

    did_process = await worker.process_one_task()

    assert did_process is True
    mock_repo.fail_task.assert_called_once()
    assert "Something went terribly wrong" in mock_repo.fail_task.call_args.kwargs["error_message"]


@pytest.mark.asyncio
async def test_task_worker_ping_handler():
    mock_repo = MagicMock(spec=TaskRepository)
    task_id = str(uuid4())
    task_record = {
        "id": task_id,
        "task_type": "ping",
        "payload": {"hello": "world"},
    }
    mock_repo.claim_next_task = AsyncMock(return_value=task_record)
    mock_repo.complete_task = AsyncMock()

    worker = TaskWorker(task_repo=mock_repo)
    did_process = await worker.process_one_task()

    assert did_process is True
    mock_repo.complete_task.assert_called_once_with(
        task_id=task_id,
        result={"pong": True, "received": {"hello": "world"}},
    )


@pytest.mark.asyncio
async def test_task_worker_run_loop_stop_event():
    mock_repo = MagicMock(spec=TaskRepository)
    mock_repo.claim_next_task = AsyncMock(return_value=None)

    stop_event = asyncio.Event()
    worker = TaskWorker(task_repo=mock_repo)

    # Schedule stop immediately after one tick
    async def set_stop():
        await asyncio.sleep(0.01)
        stop_event.set()

    asyncio.create_task(set_stop())
    await worker.run_worker_loop(poll_interval_seconds=0.01, stop_event=stop_event)

    assert stop_event.is_set()
