from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, Response, status

from app.auth import require_authorized_actor
from app.questions.models import Conversation
from app.questions.repository import ConversationRepository
from app.questions.schemas import ConversationResponse, ConversationSummaryResponse

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
    dependencies=[Depends(require_authorized_actor)],
)


@router.get("", response_model=list[ConversationSummaryResponse])
@inject
async def list_conversations(
    repository: FromDishka[ConversationRepository],
) -> list[ConversationSummaryResponse]:
    """List saved conversations, with the most recently updated conversation first."""
    conversations = await repository.list_recent()
    return [_summary(conversation) for conversation in conversations]


@router.get("/{conversation_id}", response_model=ConversationResponse)
@inject
async def get_conversation(
    conversation_id: UUID,
    repository: FromDishka[ConversationRepository],
) -> ConversationResponse:
    """Return the messages needed to view or continue a saved conversation."""
    conversation = await repository.get(conversation_id)
    return ConversationResponse.model_validate(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_conversation(
    conversation_id: UUID,
    repository: FromDishka[ConversationRepository],
) -> Response:
    """Permanently delete a saved conversation and all of its messages."""
    await repository.delete(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _summary(conversation: Conversation) -> ConversationSummaryResponse:
    first_question = next(
        (
            message.get("content", "")
            for message in conversation.messages
            if message.get("role") == "user"
        ),
        "New conversation",
    )
    title = first_question[:77] + "..." if len(first_question) > 80 else first_question
    return ConversationSummaryResponse(
        id=conversation.id,
        title=title or "New conversation",
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )
