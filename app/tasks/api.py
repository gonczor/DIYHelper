from uuid import UUID

from dishka import AsyncContainer
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth import require_authorized_actor
from app.tasks.repository import TaskNotFoundError, TaskRepository
from app.tasks.schemas import TaskResponse

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    dependencies=[Depends(require_authorized_actor)],
)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID, request: Request) -> TaskResponse:
    container: AsyncContainer = request.app.state.container
    async with container() as scope:
        repository = await scope.get(TaskRepository)
        try:
            task = await repository.get(task_id)
        except TaskNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="task not found"
            ) from error
        return TaskResponse.model_validate(task)
