from datetime import UTC, datetime

import pytest

from app.knowledge_ingestion.domain import CollectionResult, KnowledgeDocument
from app.knowledge_ingestion.service import KnowledgeIngestionService, _month_bounds


class StubSource:
    async def collect(self, start: datetime, end: datetime, on_progress=None) -> CollectionResult:
        assert start == datetime(2026, 7, 1, tzinfo=UTC)
        assert end == datetime(2026, 8, 1, tzinfo=UTC)
        if on_progress is not None:
            await on_progress(1, 1, 0)
        return CollectionResult(
            documents=[
                KnowledgeDocument(
                    source="hackaday",
                    source_id="https://hackaday.com/example/",
                    title="Example hack",
                    url="https://hackaday.com/example/",
                    content="Useful article text.",
                    published_at=datetime(2026, 7, 3, tzinfo=UTC),
                )
            ],
            discovered=1,
            failed=0,
        )


class MemoryStorage:
    def __init__(self) -> None:
        self.saved: tuple[str, bytes, str | None] | None = None

    async def save(self, path: str, content: bytes, *, content_type: str | None = None) -> str:
        self.saved = path, content, content_type
        return f"memory://{path}"


@pytest.mark.asyncio
async def test_ingest_saves_a_monthly_artifact() -> None:
    storage = MemoryStorage()
    service = KnowledgeIngestionService({"hackaday": StubSource()}, storage)

    result = await service.ingest("hackaday", "2026-07")

    assert result.artifact_uri == "memory://knowledge/hackaday/2026-07.txt"
    assert result.articles_saved == 1
    assert storage.saved is not None
    path, content, content_type = storage.saved
    assert path == "knowledge/hackaday/2026-07.txt"
    assert b"title: Example hack" in content
    assert b"Useful article text." in content
    assert content_type == "text/plain; charset=utf-8"


def test_month_requires_zero_padded_format() -> None:
    with pytest.raises(ValueError, match="YYYY-MM"):
        _month_bounds("2026-7")
