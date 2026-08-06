from collections.abc import AsyncIterator
from uuid import UUID

import structlog

from app.questions.domain import ConversationMessage, QuestionEvent
from app.questions.gemini import GeminiGatewayProtocol
from app.questions.repository import ConversationRepository
from app.storage.base import Storage

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
        storage: Storage,
        gemini: GeminiGatewayProtocol,
    ) -> None:
        self._repository: ConversationRepository = repository
        self._storage: Storage = storage
        self._gemini: GeminiGatewayProtocol = gemini

    async def answer(
        self,
        question: str,
        sources: list[str] | None,
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
                await logger.aexception(
                    "conversation summarization failed",
                    conversation_id=str(conversation.id),
                )

        artifacts = await self._load_artifacts(sources)
        yield QuestionEvent(event="metadata", conversation_id=conversation.id)

        answer = ""
        if sources != [] and not artifacts:
            answer = EMPTY_KNOWLEDGE_SCOPE_RESPONSE
            yield QuestionEvent(event="text", text=answer)
        else:
            async for text in self._gemini.stream_answer(artifacts, summary, messages):
                answer += text
                yield QuestionEvent(event="text", text=text)

        messages.append(ConversationMessage(role="model", content=answer))
        await self._repository.replace_context(conversation, messages, summary)
        yield QuestionEvent(event="done", conversation_id=conversation.id)

    async def _load_artifacts(self, sources: list[str] | None) -> list[bytes]:
        if sources == []:
            return []
        if sources is None:
            paths = await self._storage.list_items("knowledge/")
        else:
            paths = []
            for source in sources:
                paths.extend(await self._storage.list_items(f"knowledge/{source}/"))
        return [await self._storage.load(path) for path in sorted(set(paths))]
