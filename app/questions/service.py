from collections.abc import AsyncIterator
from uuid import UUID

import structlog

from app.knowledge.domain import (
    KnowledgeArticle,
    KnowledgeReference,
    KnowledgeSourceName,
    StoredKnowledgeReference,
)
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
        carried_references = self._preceding_references(messages) if sources != [] else []
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
            else await self._knowledge.select(
                question,
                sources,
                conversation.id,
                carried_references,
            )
        )
        yield QuestionEvent(event="metadata", conversation_id=conversation.id)

        answer = ""
        mode = self._answer_mode(sources, articles)
        async for text in self._gemini.stream_answer(articles, mode, summary, messages):
            answer += text
            yield QuestionEvent(event="text", text=text)

        references = [
            StoredKnowledgeReference(source=article.source, url=article.url) for article in articles
        ]
        messages.append(ConversationMessage(role="model", content=answer, references=references))
        await self._repository.replace_context(conversation, messages, summary)
        yield QuestionEvent(event="done", conversation_id=conversation.id)

    @staticmethod
    def _answer_mode(
        sources: list[KnowledgeSourceName] | None,
        articles: list[KnowledgeArticle | KnowledgeReference],
    ) -> KnowledgeAnswerMode:
        if sources == []:
            return KnowledgeAnswerMode.GENERAL
        if articles:
            return KnowledgeAnswerMode.REFERENCED
        return KnowledgeAnswerMode.EMPTY_SCOPE

    @staticmethod
    def _preceding_references(
        messages: list[ConversationMessage],
    ) -> list[StoredKnowledgeReference]:
        for message in reversed(messages):
            if message.role == "model":
                return message.references
        return []
