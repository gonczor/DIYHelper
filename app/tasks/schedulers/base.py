from typing import Protocol
from uuid import UUID


class TaskScheduler(Protocol):
    """Arrange for a durable task ID to reach a task executor.

    Implementations may use FastAPI background tasks, Celery, or a GCP service.
    They transport only the task ID; task type, parameters, status, and results
    remain in PostgreSQL and are interpreted by ``TaskExecutor``.
    """

    async def schedule(self, task_id: UUID) -> None: ...
