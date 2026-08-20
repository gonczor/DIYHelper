from collections.abc import AsyncIterator
from uuid import UUID

import structlog

from app.knowledge.domain import KnowledgeArticle, KnowledgeSourceName
from app.knowledge.service import KnowledgeSelectionService
from app.questions.domain import ConversationMessage, KnowledgeAnswerMode, QuestionEvent
from app.questions.gemini import GeminiGatewayProtocol
from app.questions.repository import ConversationRepository

SUMMARY_THRESHOLD = 20
RECENT_MESSAGES_TO_KEEP = 6

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
        mode = self._answer_mode(sources, articles)
        async for text in self._gemini.stream_answer(articles, mode, summary, messages):
            answer += text
            yield QuestionEvent(event="text", text=text)

        messages.append(ConversationMessage(role="model", content=answer))
        await self._repository.replace_context(conversation, messages, summary)
        yield QuestionEvent(event="done", conversation_id=conversation.id)

    @staticmethod
    def _answer_mode(
        sources: list[KnowledgeSourceName] | None,
        articles: list[KnowledgeArticle],
    ) -> KnowledgeAnswerMode:
        if sources == []:
            return KnowledgeAnswerMode.GENERAL
        if articles:
            return KnowledgeAnswerMode.REFERENCED
        return KnowledgeAnswerMode.EMPTY_SCOPE
