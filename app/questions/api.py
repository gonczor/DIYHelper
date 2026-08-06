from collections.abc import AsyncIterator

import structlog
from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.auth import require_authorized_actor
from app.questions.repository import ConversationNotFoundError
from app.questions.schemas import AskQuestionRequest
from app.questions.service import QuestionService

router = APIRouter(
    prefix="/questions",
    tags=["questions"],
    dependencies=[Depends(require_authorized_actor)],
)
logger = structlog.get_logger(__name__)


@router.post("")
@inject
async def ask_question(
    payload: AskQuestionRequest,
    service: FromDishka[QuestionService],
) -> StreamingResponse:
    """Stream an answer using all knowledge, a source subset, or broad model knowledge."""
    return StreamingResponse(
        stream_question_events(service, payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


async def stream_question_events(
    service: QuestionService, payload: AskQuestionRequest
) -> AsyncIterator[str]:
    try:
        async for event in service.answer(
            payload.question,
            payload.sources,
            payload.conversation_id,
        ):
            data = event.model_dump_json(exclude_none=True)
            yield f"event: {event.event}\ndata: {data}\n\n"
    except ConversationNotFoundError:
        yield _error_event("conversation not found")
    except Exception:
        await logger.aexception("question answering failed")
        yield _error_event("question answering failed")


def _error_event(message: str) -> str:
    return f'event: error\ndata: {{"event":"error","message":"{message}"}}\n\n'
