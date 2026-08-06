from dishka import AsyncContainer
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.auth import require_authorized_actor
from app.knowledge_ingestion.schemas import CreateIngestionTaskRequest
from app.tasks.repository import TaskRepository
from app.tasks.schedulers.fastapi import FastAPIBackgroundTaskScheduler
from app.tasks.schemas import TaskResponse

router = APIRouter(
    prefix="/knowledge-ingestion",
    tags=["knowledge ingestion"],
    dependencies=[Depends(require_authorized_actor)],
)


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_ingestion_task(
    payload: CreateIngestionTaskRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> TaskResponse:
    """Start a monthly knowledge ingestion task and return its persisted task record."""
    container: AsyncContainer = request.app.state.container
    target_month = payload.resolved_target_month()
    parameters = {"source": payload.source, "target_month": target_month}
    async with container() as scope:
        repository = await scope.get(TaskRepository)
        active = await repository.find_active("knowledge_ingestion", parameters)
        if active is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"an active {payload.source} task already exists for {target_month}",
            )
        task = await repository.create(
            "knowledge_ingestion", parameters, request_id=request.state.request_id
        )

    scheduler = FastAPIBackgroundTaskScheduler(background_tasks, container)
    await scheduler.schedule(task.id)
    return TaskResponse.model_validate(task)
