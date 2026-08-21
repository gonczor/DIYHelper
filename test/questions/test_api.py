import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from google import genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.domain import KnowledgeDocument, KnowledgeSourceName
from app.knowledge.models import KnowledgeArticleRecord
from app.knowledge.repository import KnowledgeRepository
from app.main import create_app
from app.questions.models import Conversation
from app.settings import Settings
from app.storage.memory import MemoryStorage


async def gemini_chunks():
    for text in ("An ESP32 ", "is a microcontroller."):
        yield SimpleNamespace(text=text)


@pytest.fixture
def retrieval_gemini_client() -> Mock:
    client = Mock()
    client.aio.models.count_tokens = AsyncMock(return_value=SimpleNamespace(total_tokens=37))
    client.aio.models.generate_content_stream = AsyncMock(return_value=gemini_chunks())
    client.aio.aclose = AsyncMock()
    return client


@pytest_asyncio.fixture
async def retrieval_http_client(
    clean_database: str,
    db_session: AsyncSession,
    retrieval_gemini_client: Mock,
) -> AsyncIterator[httpx.AsyncClient]:
    await KnowledgeRepository(db_session).upsert_documents(
        [
            KnowledgeDocument(
                source=KnowledgeSourceName.HACKADAY,
                url="https://example.test/esp32-weather",
                title="ESP32 weather station",
                content="Build a weather station with an ESP32 and a temperature sensor.",
            )
        ]
    )
    app = create_app(
        Settings(
            _env_file=None,
            auth_header="integration-secret",
            db_url=clean_database,
        ),
        gemini_client=cast(genai.Client, retrieval_gemini_client),
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_question_stream_calls_gemini_and_persists_conversation(
    clean_database: str,
    db_session: AsyncSession,
) -> None:
    gemini_client = Mock()
    gemini_client.aio.models.generate_content_stream = AsyncMock(return_value=gemini_chunks())
    gemini_client.aio.aclose = AsyncMock()
    settings = Settings(
        _env_file=None,
        auth_header="integration-secret",
        db_url=clean_database,
    )
    app = create_app(
        settings,
        storage=MemoryStorage(),
        gemini_client=cast(genai.Client, gemini_client),
    )

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/questions",
                headers={"X-Auth-Token": "integration-secret"},
                json={
                    "question": "What is an ESP32?",
                    "conversation_id": None,
                    "sources": [],
                },
            )
            unauthorized = await client.post(
                "/questions",
                json={"question": "What is an ESP32?", "sources": []},
            )

    assert response.status_code == 200
    assert unauthorized.status_code == 401
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: metadata" in response.text
    metadata_line = next(line for line in response.text.splitlines() if line.startswith("data: "))
    conversation_id = json.loads(metadata_line.removeprefix("data: "))["conversation_id"]
    UUID(conversation_id)
    assert '"text":"An ESP32 "' in response.text
    assert "event: done" in response.text
    gemini_client.aio.models.generate_content_stream.assert_awaited_once()

    conversation = await db_session.scalar(select(Conversation))

    assert conversation is not None
    assert conversation.messages == [
        {"role": "user", "content": "What is an ESP32?"},
        {"role": "model", "content": "An ESP32 is a microcontroller."},
    ]
    gemini_client.aio.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_question_without_conversation_id_returns_a_new_id(clean_database: str) -> None:
    gemini_client = Mock()
    gemini_client.aio.models.generate_content_stream = AsyncMock(return_value=gemini_chunks())
    gemini_client.aio.aclose = AsyncMock()
    app = create_app(
        Settings(
            _env_file=None,
            auth_header="integration-secret",
            db_url=clean_database,
        ),
        storage=MemoryStorage(),
        gemini_client=cast(genai.Client, gemini_client),
    )

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/questions",
                headers={"X-Auth-Token": "integration-secret"},
                json={"question": "What is an ESP32?"},
            )

    metadata_line = next(line for line in response.text.splitlines() if line.startswith("data: "))
    conversation_id = json.loads(metadata_line.removeprefix("data: "))["conversation_id"]
    UUID(conversation_id)


@pytest.mark.asyncio
async def test_question_retrieves_ranked_article_and_caches_token_count(
    retrieval_http_client: httpx.AsyncClient,
    retrieval_gemini_client: Mock,
    db_session: AsyncSession,
) -> None:
    response = await retrieval_http_client.post(
        "/questions",
        headers={"X-Auth-Token": "integration-secret"},
        json={"question": "How do I build an ESP32 weather station?"},
    )

    assert response.status_code == 200
    assert "event: done" in response.text
    metadata_line = next(line for line in response.text.splitlines() if line.startswith("data: "))
    metadata = json.loads(metadata_line.removeprefix("data: "))
    assert metadata["references"] == [
        {
            "source": "hackaday",
            "url": "https://example.test/esp32-weather",
            "title": "ESP32 weather station",
        }
    ]
    retrieval_gemini_client.aio.models.count_tokens.assert_awaited_once()
    generation_call = retrieval_gemini_client.aio.models.generate_content_stream.await_args
    reference_text = generation_call.kwargs["contents"][0].parts[0].text
    assert "ESP32 weather station" in reference_text
    assert "https://example.test/esp32-weather" in reference_text

    article = await db_session.scalar(select(KnowledgeArticleRecord))
    assert article is not None
    assert article.token_count == 37
