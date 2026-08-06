from uuid import uuid4

import pytest

from app.tasks.executor import TaskExecutor
from app.tasks.repository import TaskRepository
from app.tasks.types import TaskStatus


class StubRepository(TaskRepository):
    def __init__(self, task_type: str = "example", request_id: str | None = "request-123") -> None:
        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None
        self.task_type = task_type
        self.request_id = request_id

    async def get(self, task_id):
        return type(
            "Task",
            (),
            {
                "id": task_id,
                "type": self.task_type,
                "parameters": {"value": "input"},
                "request_id": self.request_id,
            },
        )()

    async def mark_running(self, task_id):
        self.status = TaskStatus.RUNNING

    async def mark_succeeded(self, task_id, result):
        self.status = TaskStatus.SUCCEEDED
        self.result = result

    async def update_details(self, task_id, details):
        self.details = {**getattr(self, "details", {}), **details}

    async def set_request_id(self, task_id, request_id):
        self.request_id = request_id

    async def mark_failed(self, task_id, error):
        self.status = TaskStatus.FAILED
        self.error = error


class SuccessfulHandler:
    async def __call__(self, parameters, progress):
        assert parameters == {"value": "input"}
        await progress.update({"completed": 1, "total": 2})
        return {"artifact_uri": "file:///x"}


@pytest.mark.asyncio
async def test_executor_dispatches_handler_and_records_success() -> None:
    repository = StubRepository()
    executor = TaskExecutor(repository, {"example": SuccessfulHandler()})

    await executor.execute(uuid4())

    assert repository.status is TaskStatus.SUCCEEDED
    assert repository.result == {"artifact_uri": "file:///x"}
    assert repository.details == {"completed": 1, "total": 2}


@pytest.mark.asyncio
async def test_executor_generates_and_persists_request_id_when_missing() -> None:
    repository = StubRepository(request_id=None)
    executor = TaskExecutor(repository, {"example": SuccessfulHandler()})

    await executor.execute(uuid4())

    assert repository.request_id is not None


class FailingHandler:
    async def __call__(self, parameters, progress):
        raise RuntimeError("processing failed")


@pytest.mark.asyncio
async def test_executor_records_failure_without_raising() -> None:
    repository = StubRepository()
    executor = TaskExecutor(repository, {"example": FailingHandler()})

    await executor.execute(uuid4())

    assert repository.status is TaskStatus.FAILED
    assert repository.error == {"type": "RuntimeError", "message": "processing failed"}


@pytest.mark.asyncio
async def test_executor_fails_unknown_task_type() -> None:
    repository = StubRepository(task_type="unknown")
    executor = TaskExecutor(repository, {})

    await executor.execute(uuid4())

    assert repository.status is TaskStatus.FAILED
    assert repository.error == {
        "type": "UnknownTaskTypeError",
        "message": "no handler registered for task type: unknown",
    }
