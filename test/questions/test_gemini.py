from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from google import genai

from app.questions.domain import ConversationMessage
from app.questions.gemini import (
    BROAD_KNOWLEDGE_INSTRUCTION,
    MODEL,
    RESTRICTED_KNOWLEDGE_INSTRUCTION,
    SUMMARY_INSTRUCTION,
    GeminiGateway,
)


async def chunks():
    for text in ("hello", " world"):
        yield SimpleNamespace(text=text)


@pytest.mark.asyncio
async def test_streams_expected_gemini_request() -> None:
    client = Mock()
    client.aio.models.generate_content_stream = AsyncMock(return_value=chunks())
    gateway = GeminiGateway(cast(genai.Client, client))

    result = [
        text
        async for text in gateway.stream_answer(
            [b"source document"],
            "earlier context",
            [ConversationMessage(role="user", content="question")],
        )
    ]

    assert result == ["hello", " world"]
    call = client.aio.models.generate_content_stream.await_args
    assert call.kwargs["model"] == MODEL
    assert call.kwargs["config"].system_instruction == RESTRICTED_KNOWLEDGE_INSTRUCTION
    contents = call.kwargs["contents"]
    assert contents[0].parts[0].text == "Reference documents:\nsource document"
    assert contents[1].parts[0].text == "Conversation summary:\nearlier context"
    assert contents[2].role == "user"
    assert contents[2].parts[0].text == "question"


@pytest.mark.asyncio
async def test_uses_broad_instruction_without_reference_documents() -> None:
    client = Mock()
    client.aio.models.generate_content_stream = AsyncMock(return_value=chunks())
    gateway = GeminiGateway(cast(genai.Client, client))

    _ = [
        text
        async for text in gateway.stream_answer(
            [],
            None,
            [ConversationMessage(role="user", content="question")],
        )
    ]

    call = client.aio.models.generate_content_stream.await_args
    assert call.kwargs["config"].system_instruction == BROAD_KNOWLEDGE_INSTRUCTION


@pytest.mark.asyncio
async def test_requests_expected_conversation_summary() -> None:
    client = Mock()
    client.aio.models.generate_content = AsyncMock(return_value=SimpleNamespace(text="new summary"))
    gateway = GeminiGateway(cast(genai.Client, client))

    result = await gateway.summarize(
        "old summary",
        [ConversationMessage(role="user", content="new fact")],
    )

    assert result == "new summary"
    call = client.aio.models.generate_content.await_args
    assert call.kwargs["model"] == MODEL
    assert call.kwargs["config"].system_instruction == SUMMARY_INSTRUCTION
    assert call.kwargs["contents"] == "Previous summary:\nold summary\n\nuser: new fact"
