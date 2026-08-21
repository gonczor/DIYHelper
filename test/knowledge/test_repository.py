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
    categories: list[str] | None = None,
    tags: list[str] | None = None,
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source=source,
        title=title,
        url=url,
        content=content,
        published_at=datetime(2026, 7, 3, tzinfo=UTC),
        categories=categories or [],
        tags=tags or [],
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
async def test_search_uses_or_matching_for_natural_language_fillers(
    db_session: AsyncSession,
) -> None:
    repository = KnowledgeRepository(db_session)
    await repository.upsert_documents(
        [
            document(
                url="https://example.test/atmega",
                title="ATmega328P guide",
                content="Microcontroller details.",
            )
        ]
    )

    result = await repository.search("I want info about Atmega328P", None, limit=10)

    assert [candidate.article.url for candidate in result] == ["https://example.test/atmega"]


@pytest.mark.asyncio
async def test_search_ranks_multi_term_and_exact_taxonomy_matches_first(
    db_session: AsyncSession,
) -> None:
    repository = KnowledgeRepository(db_session)
    await repository.upsert_documents(
        [
            document(
                url="https://example.test/both",
                title="Two controllers",
                content="ATmega328 and ESP32 used together.",
            ),
            document(
                url="https://example.test/one",
                title="ATmega328 project",
                content="One controller.",
            ),
            document(
                url="https://example.test/body",
                title="Controller notes",
                content="A project involving SensorBus.",
            ),
            document(
                url="https://example.test/tag",
                title="Controller notes",
                content="A project.",
                categories=["Embedded systems"],
                tags=["SensorBus"],
            ),
        ]
    )

    products = await repository.search("atmega328 or esp32", None, limit=10)
    taxonomy = await repository.search("SensorBus", None, limit=10)
    category = await repository.search("Embedded", None, limit=10)

    assert products[0].article.url == "https://example.test/both"
    assert {candidate.article.url for candidate in products} >= {
        "https://example.test/both",
        "https://example.test/one",
    }
    assert taxonomy[0].article.url == "https://example.test/tag"
    assert taxonomy[0].article.tags == ["SensorBus"]
    assert category[0].article.categories == ["Embedded systems"]


@pytest.mark.asyncio
async def test_search_supports_prefixes_and_empty_lexemes(db_session: AsyncSession) -> None:
    repository = KnowledgeRepository(db_session)
    await repository.upsert_documents(
        [
            document(
                url="https://example.test/prefix",
                title="ATmega328P board",
                content="Controller.",
            )
        ]
    )

    prefix = await repository.search("ATmega", None, limit=10)
    empty = await repository.search("the and or", None, limit=10)

    assert [candidate.article.url for candidate in prefix] == ["https://example.test/prefix"]
    assert empty == []


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

    await repository.set_token_count(changed.article.id, 84)
    await repository.upsert_documents(
        [
            document(
                url=original.url,
                title=original.title,
                content="Changed content.",
                tags=["New taxonomy"],
            )
        ]
    )
    taxonomy_changed = (await repository.search("taxonomy", None, limit=1))[0]

    assert unchanged.article.token_count == 42
    assert changed.article.token_count is None
    assert taxonomy_changed.article.token_count is None


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
