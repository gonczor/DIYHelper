from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.questions.domain import ConversationMessage
from app.questions.models import Conversation


class ConversationNotFoundError(LookupError):
    pass


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self) -> Conversation:
        conversation = Conversation(messages=[])
        self._session.add(conversation)
        await self._session.commit()
        await self._session.refresh(conversation)
        return conversation

    async def get(self, conversation_id: UUID) -> Conversation:
        conversation = await self._session.get(Conversation, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(str(conversation_id))
        return conversation

    async def replace_context(
        self,
        conversation: Conversation,
        messages: list[ConversationMessage],
        summary: str | None,
    ) -> None:
        conversation.messages = [message.model_dump() for message in messages]
        conversation.summary = summary
        await self._session.commit()
