from datetime import UTC, datetime

import httpx
import pytest

from app.knowledge_ingestion.sources.hackaday import HackadaySource


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_collects_an_article_from_a_daily_archive() -> None:
    async with httpx.AsyncClient() as client:
        source = HackadaySource(client, request_delay_seconds=0, max_articles=1)
        result = await source.collect(
            datetime(2026, 7, 1, tzinfo=UTC),
            datetime(2026, 7, 2, tzinfo=UTC),
        )

    assert result.discovered >= 1
    assert result.failed == 0
    assert len(result.documents) == 1
    document = result.documents[0]
    assert document.source == "hackaday"
    assert document.url.startswith("https://hackaday.com/2026/07/01/")
    assert document.title
    assert len(document.content) > 200
    assert document.published_at is not None


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_follows_daily_archive_pagination() -> None:
    requested_urls: list[str] = []

    async def record_request(request: httpx.Request) -> None:
        requested_urls.append(str(request.url))

    async with httpx.AsyncClient(event_hooks={"request": [record_request]}) as client:
        source = HackadaySource(client, request_delay_seconds=0, max_articles=8)
        result = await source.collect(
            datetime(2026, 7, 1, tzinfo=UTC),
            datetime(2026, 7, 2, tzinfo=UTC),
        )

    assert "https://hackaday.com/2026/07/01/" in requested_urls
    assert "https://hackaday.com/2026/07/01/page/2/" in requested_urls
    assert result.discovered == 8
    assert result.failed == 0
    assert len(result.documents) == 8
    assert all(
        document.url.startswith("https://hackaday.com/2026/07/01/") for document in result.documents
    )
