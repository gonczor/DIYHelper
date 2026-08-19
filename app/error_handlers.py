from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.auth import InvalidAuthenticationTokenError
from app.knowledge_ingestion.errors import ActiveIngestionTaskError
from app.questions.repository import ConversationNotFoundError
from app.tasks.repository import TaskNotFoundError


def register_error_handlers(application: FastAPI) -> None:
    application.add_exception_handler(
        InvalidAuthenticationTokenError, invalid_authentication_token_handler
    )
    application.add_exception_handler(ConversationNotFoundError, conversation_not_found_handler)
    application.add_exception_handler(TaskNotFoundError, task_not_found_handler)
    application.add_exception_handler(ActiveIngestionTaskError, active_ingestion_task_handler)


async def invalid_authentication_token_handler(request: Request, error: Exception) -> JSONResponse:
    return _error_response(status.HTTP_401_UNAUTHORIZED, str(error))


async def conversation_not_found_handler(request: Request, error: Exception) -> JSONResponse:
    return _error_response(status.HTTP_404_NOT_FOUND, "conversation not found")


async def task_not_found_handler(request: Request, error: Exception) -> JSONResponse:
    return _error_response(status.HTTP_404_NOT_FOUND, "task not found")


async def active_ingestion_task_handler(request: Request, error: Exception) -> JSONResponse:
    return _error_response(status.HTTP_409_CONFLICT, str(error))


def _error_response(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})
