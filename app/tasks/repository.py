from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.models import Task
from app.tasks.types import TaskStatus


class TaskNotFoundError(LookupError):
    pass


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_active(self, task_type: str, parameters: dict[str, str]) -> Task | None:
        conditions = [
            Task.type == task_type,
            Task.status.in_((TaskStatus.PENDING, TaskStatus.RUNNING)),
            *(Task.parameters[key].as_string() == value for key, value in parameters.items()),
        ]
        return await self._session.scalar(select(Task).where(*conditions))

    async def create(self, task_type: str, parameters: dict[str, Any]) -> Task:
        task = Task(type=task_type, status=TaskStatus.PENDING, parameters=parameters)
        self._session.add(task)
        await self._session.commit()
        await self._session.refresh(task)
        return task

    async def get(self, task_id: UUID) -> Task:
        task = await self._session.get(Task, task_id)
        if task is None:
            raise TaskNotFoundError(str(task_id))
        return task

    async def mark_running(self, task_id: UUID) -> None:
        task = await self.get(task_id)
        task.status = TaskStatus.RUNNING
        task.started_at = _now()
        await self._session.commit()

    async def update_details(self, task_id: UUID, details: dict[str, Any]) -> None:
        task = await self.get(task_id)
        task.details = {**task.details, **details}
        await self._session.commit()

    async def mark_succeeded(self, task_id: UUID, result: dict[str, Any]) -> None:
        task = await self.get(task_id)
        task.status = TaskStatus.SUCCEEDED
        task.result = result
        task.finished_at = _now()
        await self._session.commit()

    async def mark_failed(self, task_id: UUID, error: dict[str, Any]) -> None:
        await self._session.rollback()
        task = await self.get(task_id)
        task.status = TaskStatus.FAILED
        task.error = error
        task.finished_at = _now()
        await self._session.commit()


def _now() -> datetime:
    return datetime.now(UTC)
