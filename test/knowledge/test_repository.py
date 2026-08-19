from datetime import UTC, datetime

import pytest

from app.db import Database
from app.knowledge.domain import KnowledgeDocument
from app.knowledge.repository import KnowledgeRepository


def document(
    *,
    url: str,
    title: str,
    content: str,
    source: str = "hackaday",
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source=source,
        title=title,
        url=url,
        content=content,
        published_at=datetime(2026, 7, 3, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_upsert_and_search_rank_complete_articles(clean_database: str) -> None:
    database = Database(clean_database)
    async with database.sessions() as session:
        repository = KnowledgeRepository(session)
        await repository.upsert_documents(
            [
                document(
                    url="https://example.test/title-match",
                    title="ESP32 weather station",
                    content="A beginner electronics project.",
                ),
                document(
                    url="https://example.test/content-match",
                    title="Workshop notes",
                    content="Build an ESP32 weather station with several sensors.",
                ),
                document(
                    url="https://example.test/unrelated",
                    title="Wooden shelf",
                    content="A simple woodworking project.",
                ),
            ]
        )

        result = await repository.search("ESP32 weather station", None, limit=10)

    await database.close()
    assert [candidate.article.url for candidate in result.candidates] == [
        "https://example.test/title-match",
        "https://example.test/content-match",
    ]
    assert result.candidates[0].rank > result.candidates[1].rank > 0
    assert result.candidates[0].article.content == "A beginner electronics project."
    assert "esp32" in result.search_expression


@pytest.mark.asyncio
async def test_search_filters_sources(clean_database: str) -> None:
    database = Database(clean_database)
    async with database.sessions() as session:
        repository = KnowledgeRepository(session)
        await repository.upsert_documents(
            [
                document(
                    url="https://example.test/hackaday",
                    title="ESP32 sensor",
                    content="Hackaday article.",
                ),
                document(
                    url="https://example.test/other",
                    title="ESP32 sensor",
                    content="Other article.",
                    source="other",
                ),
            ]
        )

        result = await repository.search("ESP32", ["other"], limit=10)

    await database.close()
    assert [candidate.article.source for candidate in result.candidates] == ["other"]


@pytest.mark.asyncio
async def test_upsert_invalidates_token_count_only_when_article_changes(
    clean_database: str,
) -> None:
    database = Database(clean_database)
    original = document(
        url="https://example.test/article",
        title="Original title",
        content="Original content.",
    )
    async with database.sessions() as session:
        repository = KnowledgeRepository(session)
        await repository.upsert_documents([original])
        result = (await repository.search("Original", None, limit=1)).candidates[0]
        await repository.set_token_count(result.article.id, 42)
        await repository.upsert_documents([original])
        unchanged = (await repository.search("Original", None, limit=1)).candidates[0]

        await repository.upsert_documents(
            [
                document(
                    url=original.url,
                    title=original.title,
                    content="Changed content.",
                )
            ]
        )
        changed = (await repository.search("Changed", None, limit=1)).candidates[0]

    await database.close()
    assert unchanged.article.token_count == 42
    assert changed.article.token_count is None
