from collections.abc import AsyncIterator
from uuid import UUID

import structlog

from app.knowledge.domain import KnowledgeSourceName
from app.knowledge.service import KnowledgeSelectionService
from app.questions.domain import ConversationMessage, QuestionEvent
from app.questions.gemini import GeminiGatewayProtocol
from app.questions.repository import ConversationRepository

SUMMARY_THRESHOLD = 20
RECENT_MESSAGES_TO_KEEP = 6
EMPTY_KNOWLEDGE_SCOPE_RESPONSE = (
    "I cannot answer this based on the current knowledge scope because no reference documents "
    "were found."
)

logger = structlog.get_logger(__name__)


class QuestionService:
    def __init__(
        self,
        repository: ConversationRepository,
        knowledge: KnowledgeSelectionService,
        gemini: GeminiGatewayProtocol,
    ) -> None:
        self._repository: ConversationRepository = repository
        self._knowledge = knowledge
        self._gemini: GeminiGatewayProtocol = gemini

    async def answer(
        self,
        question: str,
        sources: list[KnowledgeSourceName] | None,
        conversation_id: UUID | None,
    ) -> AsyncIterator[QuestionEvent]:
        conversation = (
            await self._repository.get(conversation_id)
            if conversation_id is not None
            else await self._repository.create()
        )
        messages = [ConversationMessage.model_validate(item) for item in conversation.messages]
        messages.append(ConversationMessage(role="user", content=question))
        await self._repository.replace_context(conversation, messages, conversation.summary)

        summary = conversation.summary
        if len(messages) >= SUMMARY_THRESHOLD:
            older = messages[:-RECENT_MESSAGES_TO_KEEP]
            recent = messages[-RECENT_MESSAGES_TO_KEEP:]
            try:
                summary = await self._gemini.summarize(summary, older)
                messages = recent
                await self._repository.replace_context(conversation, messages, summary)
            except Exception:
                logger.exception(
                    "conversation summarization failed",
                    conversation_id=str(conversation.id),
                )

        articles = (
            []
            if sources == []
            else await self._knowledge.select(question, sources, conversation.id)
        )
        yield QuestionEvent(event="metadata", conversation_id=conversation.id)

        answer = ""
        if sources != [] and not articles:
            answer = EMPTY_KNOWLEDGE_SCOPE_RESPONSE
            yield QuestionEvent(event="text", text=answer)
        else:
            async for text in self._gemini.stream_answer(articles, summary, messages):
                answer += text
                yield QuestionEvent(event="text", text=text)

        messages.append(ConversationMessage(role="model", content=answer))
        await self._repository.replace_context(conversation, messages, summary)
        yield QuestionEvent(event="done", conversation_id=conversation.id)
