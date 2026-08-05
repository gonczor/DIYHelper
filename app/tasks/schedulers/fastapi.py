from uuid import UUID

from dishka import AsyncContainer
from fastapi import BackgroundTasks

from app.tasks.executor import TaskExecutor
from app.tasks.schedulers.base import TaskScheduler


class FastAPIBackgroundTaskScheduler(TaskScheduler):
    """Schedule execution inside the current FastAPI process.

    This intentionally unreliable hobby-project adapter can later be replaced
    by Celery or GCP. Those adapters only need to deliver ``task_id`` to a worker
    that opens a DI scope and resolves the same ``TaskExecutor``.
    """

    def __init__(self, background_tasks: BackgroundTasks, container: AsyncContainer) -> None:
        self._background_tasks = background_tasks
        self._container = container

    async def schedule(self, task_id: UUID) -> None:
        self._background_tasks.add_task(execute_task, self._container, task_id)


async def execute_task(container: AsyncContainer, task_id: UUID) -> None:
    """Open an execution scope and run a task by its durable identifier."""
    async with container() as scope:
        executor = await scope.get(TaskExecutor)
        await executor.execute(task_id)
