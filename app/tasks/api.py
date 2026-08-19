from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends

from app.auth import require_authorized_actor
from app.tasks.repository import TaskRepository
from app.tasks.schemas import TaskResponse

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    dependencies=[Depends(require_authorized_actor)],
)


@router.get("/{task_id}", response_model=TaskResponse)
@inject
async def get_task(
    task_id: UUID,
    repository: FromDishka[TaskRepository],
) -> TaskResponse:
    """Return the current status, progress details, and result of a persisted task."""
    task = await repository.get(task_id)
    return TaskResponse.model_validate(task)
