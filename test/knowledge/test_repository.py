from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.domain import KnowledgeDocument, KnowledgeSourceName, StoredKnowledgeReference
from app.knowledge.repository import KnowledgeRepository


def document(
    *,
    url: str,
    title: str,
    content: str,
    source: KnowledgeSourceName = KnowledgeSourceName.HACKADAY,
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source=source,
        title=title,
        url=url,
        content=content,
        published_at=datetime(2026, 7, 3, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_upsert_and_search_rank_complete_articles(db_session: AsyncSession) -> None:
    repository = KnowledgeRepository(db_session)
    await repository.upsert_documents(
        [
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
            document(
                url="https://example.test/title-match",
                title="ESP32 weather station",
                content="A beginner electronics project.",
            ),
        ]
    )

    result = await repository.search("ESP32 weather station", None, limit=10)

    assert [candidate.article.url for candidate in result] == [
        "https://example.test/title-match",
        "https://example.test/content-match",
    ]
    assert result[0].rank > result[1].rank > 0
    assert result[0].article.content == "A beginner electronics project."


@pytest.mark.asyncio
async def test_search_filters_sources(db_session: AsyncSession) -> None:
    repository = KnowledgeRepository(db_session)
    await repository.upsert_documents(
        [
            document(
                url="https://example.test/hackaday",
                title="ESP32 sensor",
                content="Hackaday article.",
            )
        ]
    )

    result = await repository.search("ESP32", [KnowledgeSourceName.HACKADAY], limit=10)

    assert [candidate.article.source for candidate in result] == [KnowledgeSourceName.HACKADAY]


@pytest.mark.asyncio
async def test_upsert_invalidates_token_count_only_when_article_changes(
    db_session: AsyncSession,
) -> None:
    original = document(
        url="https://example.test/article",
        title="Original title",
        content="Original content.",
    )
    repository = KnowledgeRepository(db_session)
    await repository.upsert_documents([original])
    result = (await repository.search("Original", None, limit=1))[0]
    await repository.set_token_count(result.article.id, 42)
    await repository.upsert_documents([original])
    unchanged = (await repository.search("Original", None, limit=1))[0]

    await repository.upsert_documents(
        [
            document(
                url=original.url,
                title=original.title,
                content="Changed content.",
            )
        ]
    )
    changed = (await repository.search("Changed", None, limit=1))[0]

    assert unchanged.article.token_count == 42
    assert changed.article.token_count is None


@pytest.mark.asyncio
async def test_finds_persisted_articles_by_source_and_url(db_session: AsyncSession) -> None:
    repository = KnowledgeRepository(db_session)
    await repository.upsert_documents(
        [document(url="https://example.test/kept", title="Kept", content="Evidence")]
    )

    result = await repository.find_by_references(
        [
            StoredKnowledgeReference(
                source=KnowledgeSourceName.HACKADAY,
                url="https://example.test/kept",
            ),
            StoredKnowledgeReference(
                source=KnowledgeSourceName.HACKADAY,
                url="https://example.test/missing",
            ),
        ]
    )

    assert [article.url for article in result] == ["https://example.test/kept"]
