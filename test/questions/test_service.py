from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.knowledge.domain import KnowledgeArticle, KnowledgeSourceName, StoredKnowledgeReference
from app.questions.domain import ConversationMessage, KnowledgeAnswerMode
from app.questions.service import QuestionService


class StubConversationRepository:
    def __init__(self, messages=None, summary=None) -> None:
        self.conversation = SimpleNamespace(
            id=uuid4(),
            messages=messages or [],
            summary=summary,
        )
        self.replacements = []

    async def create(self):
        return self.conversation

    async def get(self, conversation_id):
        assert conversation_id == self.conversation.id
        return self.conversation

    async def replace_context(self, conversation, messages, summary):
        conversation.messages = [message.model_dump(exclude_defaults=True) for message in messages]
        conversation.summary = summary
        self.replacements.append((list(messages), summary))


class StubGemini:
    def __init__(self) -> None:
        self.answer_calls = []
        self.summary_calls = []

    async def summarize(self, previous_summary, messages):
        self.summary_calls.append((previous_summary, messages))
        return "condensed history"

    async def stream_answer(self, articles, mode, summary, messages):
        self.answer_calls.append((articles, mode, summary, list(messages)))
        yield "first "
        yield "second"


class StubKnowledgeSelection:
    def __init__(self, articles=None) -> None:
        self.articles = articles or []
        self.calls = []

    async def select(self, query, sources, conversation_id, carried_references=None):
        self.calls.append((query, sources, conversation_id, carried_references or []))
        return self.articles


def article(number: int) -> KnowledgeArticle:
    return KnowledgeArticle(
        id=uuid4(),
        source=KnowledgeSourceName.HACKADAY,
        url=f"https://example.test/{number}",
        title=f"Article {number}",
        content=f"Content {number}",
    )


@pytest.mark.asyncio
async def test_empty_sources_uses_broad_knowledge_and_persists_complete_messages() -> None:
    repository = StubConversationRepository()
    gemini = StubGemini()
    knowledge = StubKnowledgeSelection()
    service = QuestionService(repository, knowledge, gemini)

    events = [event async for event in service.answer("What is ESP32?", [], None)]

    assert [event.event for event in events] == ["metadata", "text", "text", "done"]
    articles, mode, summary, sent_messages = gemini.answer_calls[0]
    assert articles == []
    assert mode is KnowledgeAnswerMode.GENERAL
    assert knowledge.calls == []
    assert summary is None
    assert sent_messages == [ConversationMessage(role="user", content="What is ESP32?")]
    assert repository.conversation.messages[-1] == {
        "role": "model",
        "content": "first second",
    }


@pytest.mark.asyncio
async def test_loads_ranked_articles_for_selected_sources() -> None:
    selected = [article(1), article(2)]
    knowledge = StubKnowledgeSelection(selected)
    gemini = StubGemini()
    repository = StubConversationRepository()
    service = QuestionService(repository, knowledge, gemini)

    _ = [event async for event in service.answer("Projects?", [KnowledgeSourceName.HACKADAY], None)]

    assert gemini.answer_calls[0][0] == selected
    assert gemini.answer_calls[0][1] is KnowledgeAnswerMode.REFERENCED
    assert knowledge.calls == [
        ("Projects?", [KnowledgeSourceName.HACKADAY], repository.conversation.id, [])
    ]


@pytest.mark.asyncio
async def test_omitted_sources_searches_every_source() -> None:
    selected = [article(1)]
    knowledge = StubKnowledgeSelection(selected)
    gemini = StubGemini()
    repository = StubConversationRepository()
    service = QuestionService(repository, knowledge, gemini)

    _ = [event async for event in service.answer("Projects?", None, None)]

    assert gemini.answer_calls[0][0] == selected
    assert gemini.answer_calls[0][1] is KnowledgeAnswerMode.REFERENCED
    assert knowledge.calls == [("Projects?", None, repository.conversation.id, [])]


@pytest.mark.asyncio
async def test_carries_preceding_assistant_references_and_persists_selected_urls() -> None:
    previous = StoredKnowledgeReference(
        source=KnowledgeSourceName.HACKADAY,
        url="https://example.test/previous",
    )
    selected = [article(2)]
    repository = StubConversationRepository(
        messages=[
            {"role": "user", "content": "Atmel?"},
            {
                "role": "model",
                "content": "Atmel makes microcontrollers.",
                "references": [previous.model_dump(mode="json")],
            },
        ]
    )
    knowledge = StubKnowledgeSelection(selected)
    service = QuestionService(repository, knowledge, StubGemini())

    _ = [
        event
        async for event in service.answer(
            "Tell me more", [KnowledgeSourceName.HACKADAY], repository.conversation.id
        )
    ]

    assert knowledge.calls == [
        (
            "Tell me more",
            [KnowledgeSourceName.HACKADAY],
            repository.conversation.id,
            [previous],
        )
    ]
    assert repository.conversation.messages[-1]["references"] == [
        {
            "source": KnowledgeSourceName.HACKADAY,
            "url": selected[0].url,
        }
    ]


@pytest.mark.asyncio
async def test_general_knowledge_neither_carries_nor_persists_references() -> None:
    repository = StubConversationRepository(
        messages=[
            {
                "role": "model",
                "content": "Earlier answer",
                "references": [
                    {
                        "source": KnowledgeSourceName.HACKADAY,
                        "url": "https://example.test/previous",
                    }
                ],
            }
        ]
    )
    knowledge = StubKnowledgeSelection()
    service = QuestionService(repository, knowledge, StubGemini())

    _ = [event async for event in service.answer("New topic", [], repository.conversation.id)]

    assert knowledge.calls == []
    assert "references" not in repository.conversation.messages[-1]


@pytest.mark.asyncio
async def test_empty_requested_knowledge_scope_lets_model_decide_without_broad_knowledge() -> None:
    repository = StubConversationRepository()
    gemini = StubGemini()
    service = QuestionService(repository, StubKnowledgeSelection(), gemini)

    events = [
        event async for event in service.answer("Projects?", [KnowledgeSourceName.HACKADAY], None)
    ]

    assert [event.event for event in events] == ["metadata", "text", "text", "done"]
    articles, mode, summary, sent_messages = gemini.answer_calls[0]
    assert articles == []
    assert mode is KnowledgeAnswerMode.EMPTY_SCOPE
    assert summary is None
    assert sent_messages == [ConversationMessage(role="user", content="Projects?")]
    assert repository.conversation.messages[-1] == {
        "role": "model",
        "content": "first second",
    }


@pytest.mark.asyncio
async def test_summarizes_old_messages_and_keeps_latest_six() -> None:
    existing = [
        ConversationMessage(
            role="user" if index % 2 == 0 else "model",
            content=f"message {index}",
        ).model_dump()
        for index in range(19)
    ]
    repository = StubConversationRepository(existing, summary="previous summary")
    gemini = StubGemini()
    service = QuestionService(repository, StubKnowledgeSelection(), gemini)

    _ = [event async for event in service.answer("new question", [], repository.conversation.id)]

    previous_summary, summarized = gemini.summary_calls[0]
    assert previous_summary == "previous summary"
    assert len(summarized) == 14
    _, _, summary, sent_messages = gemini.answer_calls[0]
    assert summary == "condensed history"
    assert len(sent_messages) == 6
    assert sent_messages[-1].content == "new question"


@pytest.mark.asyncio
async def test_does_not_persist_partial_assistant_answer() -> None:
    class FailingGemini(StubGemini):
        async def stream_answer(self, articles, mode, summary, messages):
            yield "partial"
            raise RuntimeError("generation failed")

    repository = StubConversationRepository()
    service = QuestionService(repository, StubKnowledgeSelection(), FailingGemini())

    with pytest.raises(RuntimeError, match="generation failed"):
        _ = [event async for event in service.answer("question", [], None)]

    assert repository.conversation.messages == [{"role": "user", "content": "question"}]


@pytest.mark.asyncio
async def test_uses_complete_history_when_summarization_fails() -> None:
    class SummaryFailingGemini(StubGemini):
        async def summarize(self, previous_summary, messages):
            raise RuntimeError("summary failed")

    existing = [
        ConversationMessage(role="user", content=f"message {index}").model_dump()
        for index in range(19)
    ]
    repository = StubConversationRepository(existing)
    gemini = SummaryFailingGemini()
    service = QuestionService(repository, StubKnowledgeSelection(), gemini)

    _ = [event async for event in service.answer("new question", [], None)]

    assert len(gemini.answer_calls[0][3]) == 20


@pytest.mark.asyncio
async def test_closing_stream_does_not_persist_partial_assistant_answer() -> None:
    repository = StubConversationRepository()
    service = QuestionService(repository, StubKnowledgeSelection(), StubGemini())
    stream = service.answer("question", [], None)

    assert (await anext(stream)).event == "metadata"
    assert (await anext(stream)).event == "text"
    await stream.aclose()

    assert repository.conversation.messages == [{"role": "user", "content": "question"}]
