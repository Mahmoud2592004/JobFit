"""
Asynchronous Durable Task Worker Engine.
Polls PostgreSQL task queue, executes registered task handlers,
and manages exponential backoff and failure states.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import structlog

from app.repositories.task_repository import TaskRepository

log = structlog.get_logger(__name__)

TaskHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class TaskWorker:
    """Asynchronous worker pulling and executing durable background jobs."""

    def __init__(
        self,
        task_repo: TaskRepository,
        worker_id: str | None = None,
    ) -> None:
        self.task_repo = task_repo
        self.worker_id = worker_id or f"worker-{uuid4().hex[:8]}"
        self._handlers: dict[str, TaskHandler] = {}

        # Register default internal handlers
        self.register_handler("ping", self._handle_ping)

    def register_handler(self, task_type: str, handler: TaskHandler) -> None:
        """Register an async handler callable for a specific task type."""
        self._handlers[task_type] = handler

    async def _handle_ping(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Simple health/heartbeat ping task handler."""
        return {"pong": True, "received": payload}

    async def process_one_task(self) -> bool:
        """
        Attempt to claim and process a single pending task from the queue.
        Returns True if a task was processed, False if queue was empty.
        """
        task = await self.task_repo.claim_next_task(worker_id=self.worker_id)
        if not task:
            return False

        task_id = str(task["id"])
        task_type = str(task.get("task_type", ""))
        payload = task.get("payload", {})

        log.info(
            "task_processing_started",
            worker_id=self.worker_id,
            task_id=task_id,
            task_type=task_type,
        )

        handler = self._handlers.get(task_type)
        if not handler:
            err_msg = f"No handler registered for task type '{task_type}'"
            log.error("task_handler_missing", task_id=task_id, task_type=task_type)
            await self.task_repo.fail_task(task_id=task_id, error_message=err_msg)
            return True

        try:
            result = await handler(payload)
            await self.task_repo.complete_task(task_id=task_id, result=result)
            log.info("task_processing_completed", task_id=task_id, worker_id=self.worker_id)
        except Exception as exc:
            log.error(
                "task_execution_failed",
                task_id=task_id,
                worker_id=self.worker_id,
                error=str(exc),
            )
            await self.task_repo.fail_task(task_id=task_id, error_message=str(exc))

        return True

    async def run_worker_loop(
        self,
        poll_interval_seconds: float = 2.0,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Continuously poll queue until stop_event is set."""
        log.info("task_worker_loop_started", worker_id=self.worker_id)
        while stop_event is None or not stop_event.is_set():
            try:
                processed = await self.process_one_task()
                if not processed:
                    await asyncio.sleep(poll_interval_seconds)
            except Exception as exc:
                log.error("worker_loop_error", worker_id=self.worker_id, error=str(exc))
                await asyncio.sleep(poll_interval_seconds)
