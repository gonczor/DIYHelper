import time
from uuid import UUID

import structlog
from structlog.typing import FilteringBoundLogger

from app.tasks.handlers import TaskHandler
from app.tasks.repository import TaskRepository


class UnknownTaskTypeError(RuntimeError):
    pass


class RepositoryTaskProgress:
    def __init__(self, repository: TaskRepository, task_id: UUID) -> None:
        self._repository = repository
        self._task_id = task_id

    async def update(self, details: dict[str, object]) -> None:
        await self._repository.update_details(self._task_id, details)


class TaskExecutor:
    """Execute a persisted task without knowing its business operation.

    Every execution adapter calls the same ``execute(task_id)`` entry point. The
    current FastAPI adapter invokes it in-process; a future Celery worker or GCP
    function can create the application container and invoke it with the task ID
    from its message. Only the scheduling adapter changes.

    The executor loads the durable task, resolves its handler by ``task.type``,
    records lifecycle transitions, and stores the handler's JSON-compatible
    result or error. Queue messages therefore need to contain only a task ID,
    never a serialized Python callable or request-scoped dependency.
    """

    def __init__(
        self,
        repository: TaskRepository,
        handlers: dict[str, TaskHandler],
        logger: FilteringBoundLogger,
    ) -> None:
        self._repository = repository
        self._handlers = handlers
        self._logger = logger

    async def execute(self, task_id: UUID) -> None:
        task = await self._repository.get(task_id)
        logger = self._logger.bind(task_id=str(task_id), task_type=task.type)
        started_at = time.perf_counter()
        try:
            handler = self._handlers.get(task.type)
            if handler is None:
                raise UnknownTaskTypeError(f"no handler registered for task type: {task.type}")
            await self._repository.mark_running(task_id)
            await logger.ainfo("task started")
            result = await handler(
                task.parameters,
                RepositoryTaskProgress(self._repository, task_id),
            )
            await self._repository.mark_succeeded(task_id, result)
            await logger.ainfo("task completed", duration_seconds=time.perf_counter() - started_at)
        except Exception as error:
            await self._repository.mark_failed(
                task_id,
                {"type": type(error).__name__, "message": str(error)},
            )
            await logger.aexception(
                "task failed",
                duration_seconds=time.perf_counter() - started_at,
            )


def get_task_logger() -> FilteringBoundLogger:
    return structlog.get_logger("tasks")
