import time
from uuid import UUID, uuid4

import structlog
from structlog.typing import FilteringBoundLogger

from app.observability.context import bind_request_id
from app.tasks.handlers import TaskHandler
from app.tasks.models import Task
from app.tasks.repository import TaskRepository

logger = structlog.get_logger(__name__)


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
    ) -> None:
        self._repository = repository
        self._handlers = handlers

    async def execute(self, task_id: UUID) -> None:
        task = await self._repository.get(task_id)
        request_id = task.request_id or str(uuid4())
        if task.request_id is None:
            await self._repository.set_request_id(task_id, request_id)
        await self._execute_with_logging_context(task, request_id)

    async def _execute_with_logging_context(
        self,
        task: Task,
        request_id: str,
    ) -> None:
        """Keep logging context management outside the task lifecycle logic."""
        with bind_request_id(request_id):
            task_logger = logger.bind(task_id=str(task.id), task_type=task.type)
            await self._execute_task(task, task_logger)

    async def _execute_task(self, task: Task, logger: FilteringBoundLogger) -> None:
        started_at = time.perf_counter()
        try:
            handler = self._handlers.get(task.type)
            if handler is None:
                raise UnknownTaskTypeError(f"no handler registered for task type: {task.type}")
            await self._repository.mark_running(task.id)
            await logger.ainfo("task started")
            result = await handler(
                task.parameters,
                RepositoryTaskProgress(self._repository, task.id),
            )
            await self._repository.mark_succeeded(task.id, result)
            await logger.ainfo("task completed", duration_seconds=time.perf_counter() - started_at)
        except Exception as error:
            await self._repository.mark_failed(
                task.id,
                {"type": type(error).__name__, "message": str(error)},
            )
            await logger.aexception(
                "task failed",
                duration_seconds=time.perf_counter() - started_at,
            )
